#!/bin/sh

cat <<EOF >> /etc/apt/sources.list
deb http://security.debian.org/ testing-security main
deb http://ftp.us.debian.org/debian testing-updates main
deb http://ftp.us.debian.org/debian testing main
EOF

cat <<EOF > /etc/apt/preferences.d/apt.pref
Package: *
Pin: release a=stable
Pin-Priority: 900

Package: *
Pin: release a=testing
Pin-Priority: -2
EOF
