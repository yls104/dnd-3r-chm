#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Word-exported HTML files: remove inline styles, class, lang attributes,
mso custom tags, and <style> blocks. Keep <img> tags untouched.
"""

import os
import re
import sys
import argparse
import shutil


def clean_html(content):
    """Clean redundant attributes and styles from HTML, keeping <img> tags intact."""

    # 1. Remove <style>...</style> blocks (including comments)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

    # 2. Remove mso/word custom tags like <o:p>, </o:p>, <u1:p>, </u1:p>, <st1:*, etc.
    # Must do this BEFORE clean_tag processes attributes, otherwise <o:p> becomes <o p>
    content = re.sub(r'</?[a-z]\d*:[a-z][^>]*>', '', content, flags=re.IGNORECASE)
    # Also remove Word namespace tags like <st1:place>, </st1:place>, etc.
    content = re.sub(r'</?[a-z]+\d*:[a-z]+[^>]*>', '', content, flags=re.IGNORECASE)

    # 3. Process attributes on non-<img> tags
    def clean_tag(match):
        full_match = match.group(0)
        # If <img tag, don't touch
        if re.match(r'<img\b', full_match, re.IGNORECASE):
            return full_match
        # If <meta tag, don't touch
        if re.match(r'<meta\b', full_match, re.IGNORECASE):
            return full_match
        # If closing tag, return as-is
        if full_match.startswith('</'):
            return full_match

        # Extract tag name
        tag_name_match = re.match(r'<(\w+)', full_match)
        if not tag_name_match:
            return full_match
        tag_name = tag_name_match.group(1).lower()

        # Extract inner part (between tag name and closing >)
        inner = re.sub(r'^<\w+', '', full_match, count=1)
        if inner.endswith('/>'):
            inner = inner[:-2]
            closing = '/>'
        elif inner.endswith('>'):
            inner = inner[:-1]
            closing = '>'
        else:
            return full_match

        # Find all attribute key-value pairs
        attr_kv_pattern = re.compile(
            r'(\w[\w-]*)'           # attribute name
            r'(?:\s*=\s*'           # equals sign
            r'(?:"[^"]*"|\'[^\']*\'|[^\s>]+)'  # attribute value
            r')?',
            re.UNICODE
        )

        kept_kv = []
        for m in attr_kv_pattern.finditer(inner):
            attr_name = m.group(1)
            attr_lower = attr_name.lower()
            # Remove class, style, lang attributes
            if attr_lower in ('class', 'style', 'lang'):
                continue
            # Remove all mso-* attributes
            if attr_lower.startswith('mso-'):
                continue
            kept_kv.append(m.group(0).strip())

        new_inner = ' '.join(kept_kv)
        if new_inner:
            result = '<%s %s%s' % (tag_name, new_inner, closing)
        else:
            result = '<%s%s' % (tag_name, closing)

        return result

    # Process all tags
    content = re.sub(
        r'<(?:\w+[^>]*|/\w+[^>]*)>',
        clean_tag,
        content,
        flags=re.DOTALL
    )

    # 4. Remove empty <span></span> tags (multiple passes for nesting)
    for _ in range(5):
        content = re.sub(r'<span>\s*</span>', '', content, flags=re.IGNORECASE)

    # 5. Remove <span>&nbsp;</span>
    content = re.sub(r'<span>&nbsp;</span>', '', content, flags=re.IGNORECASE)

    # 6. Compress multiple blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


def process_file(filepath, dry_run=False, backup=False):
    """Process a single file."""
    # Try gb2312 first (common for these files), then utf-8
    content = None
    encoding_used = None
    for enc in ('gb2312', 'gb18030', 'utf-8'):
        try:
            with open(filepath, 'r', encoding=enc, errors='strict') as f:
                content = f.read()
            encoding_used = enc
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if content is None:
        # Last resort: read with replacement
        try:
            with open(filepath, 'r', encoding='gb18030', errors='replace') as f:
                content = f.read()
            encoding_used = 'gb18030'
        except Exception as e:
            print("  Skip (cannot read): %s - %s" % (filepath, e))
            return False

    original_size = len(content)
    cleaned = clean_html(content)
    cleaned_size = len(cleaned)

    if original_size == cleaned_size:
        print("  No change: %s" % filepath)
        return False

    reduction = original_size - cleaned_size
    pct = (reduction / original_size) * 100
    prefix = "[DRY-RUN] " if dry_run else ""
    print("  %s%s" % (prefix, filepath))
    print("    %d -> %d bytes (reduced %d bytes, %.1f%%)" % (original_size, cleaned_size, reduction, pct))

    if not dry_run:
        if backup:
            backup_path = filepath + '.bak'
            if not os.path.exists(backup_path):
                shutil.copy2(filepath, backup_path)
        with open(filepath, 'w', encoding=encoding_used, errors='replace') as f:
            f.write(cleaned)

    return True


def main():
    parser = argparse.ArgumentParser(
        description='Clean Word-exported HTML: remove styles/attrs, keep <img> intact'
    )
    parser.add_argument('path', help='File or directory path to process')
    parser.add_argument('--ext', default='htm,html', help='File extensions to process, comma-separated (default: htm,html)')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not modify files')
    parser.add_argument('--backup', action='store_true', help='Create .bak backup before modifying')
    args = parser.parse_args()

    target = args.path
    extensions = ['.' + e.strip().lstrip('.') for e in args.ext.split(',')]

    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        files = []
        for root, dirs, filenames in os.walk(target):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in extensions:
                    files.append(os.path.join(root, fn))
    else:
        print("Path not found: %s" % target)
        sys.exit(1)

    print("Found %d files to process" % len(files))
    if args.dry_run:
        print("[DRY-RUN MODE] Files will not be modified")

    changed = 0
    for fp in files:
        if process_file(fp, dry_run=args.dry_run, backup=args.backup):
            changed += 1

    print("\nDone: %d/%d files modified" % (changed, len(files)))


if __name__ == '__main__':
    main()
