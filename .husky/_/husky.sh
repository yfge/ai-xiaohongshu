#!/bin/sh
# shellcheck shell=sh

if [ -z "$husky_skip_init" ]; then
  if [ "$HUSKY_DEBUG" = "1" ]; then
    set -x
  fi

  export HUSKY=1
  readonly hook_name="$(basename "$0")"
  readonly husky_dir="$(dirname "$0")/_"
  readonly husky_root="$(dirname "$(dirname "$0")")"
  export PATH="$husky_root/node_modules/.bin:$PATH"

  if [ -f "$husky_dir/husky.local.sh" ]; then
    . "$husky_dir/husky.local.sh"
  fi

  if [ -f "$husky_dir/$hook_name" ]; then
    sh "$husky_dir/$hook_name" "$@"
    exit $?
  fi
fi
