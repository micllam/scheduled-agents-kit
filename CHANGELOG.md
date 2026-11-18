# Changelog

All notable changes to scheduled-agents-kit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-18

### Added

- The prompt of a task can be composed from several prompt files by setting the
  manifest field `prompt` to a list.

## [0.2.0] - 2026-11-16

### Added

- The optional manifest field `chat_project_id` places a task in a claude.ai
  project, whose documents a run can read and write. A deployment stops when an
  existing task's project differs from its entry.

## [0.1.0] - 2026-11-14

Initial release.
