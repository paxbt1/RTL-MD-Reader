#!/usr/bin/env bash
set -euo pipefail
umask 022

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '\n' < "$project_dir/VERSION")"
package_name="persian-md-reader"
stage_dir="$(mktemp -d)"
trap 'rm -rf "$stage_dir"' EXIT
chmod 0755 "$stage_dir"

mkdir -p "$stage_dir/DEBIAN" \
  "$stage_dir/usr/bin" \
  "$stage_dir/usr/share/$package_name/public" \
  "$stage_dir/usr/share/applications" \
  "$stage_dir/usr/share/icons/hicolor/scalable/apps" \
  "$stage_dir/usr/lib/systemd/user" \
  "$stage_dir/usr/share/doc/$package_name" \
  "$project_dir/dist"

install -m 0755 "$project_dir/packaging/$package_name" "$stage_dir/usr/bin/$package_name"
install -m 0644 "$project_dir/app.py" "$stage_dir/usr/share/$package_name/app.py"
install -m 0644 "$project_dir/public/index.html" "$project_dir/public/style.css" \
  "$project_dir/public/app.js" "$project_dir/public/vazirmatn.woff2" \
  "$stage_dir/usr/share/$package_name/public/"
install -m 0644 "$project_dir/public/OFL-Vazirmatn.txt" "$stage_dir/usr/share/doc/$package_name/"
install -m 0644 "$project_dir/LICENSE" "$stage_dir/usr/share/doc/$package_name/copyright"
install -m 0644 "$project_dir/README.md" "$stage_dir/usr/share/doc/$package_name/README.md"
install -m 0644 "$project_dir/packaging/$package_name.desktop" "$stage_dir/usr/share/applications/"
install -m 0644 "$project_dir/packaging/$package_name.svg" "$stage_dir/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 "$project_dir/packaging/$package_name.service" "$stage_dir/usr/lib/systemd/user/"

cat > "$stage_dir/DEBIAN/control" <<EOF
Package: $package_name
Version: $version
Section: editors
Priority: optional
Architecture: all
Maintainer: Persian Markdown Reader contributors <noreply@users.noreply.github.com>
Depends: python3, python3-markdown (>= 3.3.6), xdg-utils, systemd
Description: Lightweight Persian Markdown editor and reader
 A local browser-based Markdown editor with live RTL preview, Vazirmatn font,
 tables, paragraph alignment, and PDF printing.
EOF

output="$project_dir/dist/${package_name}_${version}_all.deb"
dpkg-deb --build --root-owner-group "$stage_dir" "$output"
echo "Built $output"
