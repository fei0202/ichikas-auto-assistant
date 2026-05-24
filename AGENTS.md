# Skill Usage Guide

This repo provides three local skills:

- `kotonebot-emulator-debug`
- `kotonebot-vision-debug`
- `iaa-task-integration`
- `iaa-template-resource-integration`

Use them deliberately. They solve different parts of the problem.

## Code Style

- Use the repo `.venv` for Python scripts, probes, generators, and validation commands.
- Do not over-split functions. If a helper is called only once, keep the logic inline unless the extracted function is genuinely complex or materially improves readability.
- When adding reusable image templates, prefer the standard `resources/ -> tools/make_resources.py -> iaa.tasks.R` flow over ad-hoc file loading.

### QML: ComboBox vs Select

Use `Select` (`iaa/application/framework/dsl/qml/controls/Select.qml`) instead of `ComboBox` for all non-editable dropdowns. `Select` is a FluentWinUI3 ComboBox in select mode with corrected item highlight behavior: the accent bar only appears on the currently selected item; hovering other items changes their background color without showing an accent bar.

- **Non-editable dropdown** → use `Select`
- **Editable ComboBox** (`editable: true`) → keep using `ComboBox`

Import path examples (adjust `..` depth to match the file's location):
- Same directory as `Select.qml`: no import needed
- From `iaa/application/qt/qml/**/`: `import "../../../framework/dsl/qml/controls"`

## `kotonebot-emulator-debug`

Use this skill when the task is about live interaction with the emulator or reproducing behavior on a real page.

Typical triggers:

- connect to MuMu
- initialize kotonebot context
- capture live screenshots
- click, swipe, or scroll the device
- poll page state after an action
- reproduce a failure on the real UI
- save runtime artifacts under `logs/`

Good examples:

- "Why does this click not switch tabs on the emulator?"
- "Scroll the list and capture a few frames."
- "Reproduce this page recognition failure live."

This skill is about runtime access and reproducible live probes.
It is not the best place for deep HSV / mask / contour analysis by itself.

## `kotonebot-vision-debug`

Use this skill when the task is about understanding or improving visual recognition logic.

Typical triggers:

- choose or validate ROI / search zone
- tune HSV thresholds
- inspect mask quality
- compare `open` / `close` morphology effects
- inspect contours and candidate scores
- determine whether the detector is targeting the right visual object
- compare two recognition strategies on the same frame
- validate recognition across scroll states or page states

Good examples:

- "Why is this item rect merging with the row above?"
- "Why is the icon rect inside the icon instead of around it?"
- "Would white / non-white segmentation work better here than edges?"

This skill is about visual semantics and detector behavior.
It usually works best on saved frames or controlled live captures.

## `iaa-task-integration`

Use this skill when the task is about adding or updating an IAA task by wiring everything around the task implementation itself.

Typical triggers:

- add a new task placeholder
- register a task in `iaa/tasks/registry.py`
- decide whether a task is regular or manual
- add scheduler enable switches
- extend config models in `iaa/config/schemas.py` and `iaa/config/base.py`
- update existing `conf/*.json` files
- expose task settings in the desktop GUI
- verify a new task is reachable from CLI and GUI

Good examples:

- "新增一个任务占位，把配置和 GUI 接好。"
- "给 IAA 加一个常规任务，不写逻辑，只把注册和设置项补全。"
- "帮我把一个新任务接到 registry、scheduler 和桌面端。"

This skill is about integration workflow and repo conventions.
It is not the place for implementing the task's business logic itself.

## `iaa-template-resource-integration`

Use this skill when the task is about turning a discovered image patch into a formal IAA template resource that should be loaded through the generated `R.py` flow.

Typical triggers:

- add a new template under `resources/`
- create or update a `*.png.json` resource definition
- run `tools/make_resources.py`
- verify a generated prefab appears in `iaa/tasks/R.py`
- switch business code from ad-hoc file loading to `R.*` resources
- decide whether a captured image should stay in `logs/` or become a formal template

Good examples:

- "把这张截图接入 resources 和 R.py。"
- "新增一个模板资源，不要手写路径。"
- "帮我把 logs 里的图做成正式 prefab。"

This skill is about the repository's template resource workflow.
It is not the place for vision algorithm tuning or live emulator reproduction.

## Use Both Together

Use both skills when the task starts with a live emulator problem and then turns into a recognition-analysis problem.

This is the common workflow for UI automation bugs:

1. Use `kotonebot-emulator-debug` to reproduce the issue, scroll if needed, and save the failing frames.
2. Use `kotonebot-vision-debug` to analyze those frames with ROI, HSV, masks, morphology, contours, and side-by-side probes.
3. Patch the implementation.
4. Return to `kotonebot-emulator-debug` to verify the fix on the real emulator across multiple states.

Use `kotonebot-vision-debug` and `iaa-template-resource-integration` together when the task starts as detector analysis and ends with adding a reusable template asset to the repository.

This is the common workflow for template-backed vision work:

1. Use `kotonebot-vision-debug` to inspect the target visually and decide whether a template strategy is appropriate.
2. Save or crop the exact image patch that should become the template.
3. Use `iaa-template-resource-integration` to place the asset under `resources/`, add the meta file, run `tools/make_resources.py`, and switch code to `iaa.tasks.R`.
4. Re-run the detector or task code to verify the generated resource works end to end.

## Which Skill First

Start with `kotonebot-emulator-debug` if:

- you do not yet have the failing frame
- the bug may involve timing, clicking, scrolling, or page transitions
- you are not sure the issue is purely visual

Start with `kotonebot-vision-debug` if:

- you already have the failing screenshot
- the bug is clearly in ROI / mask / contour / scoring logic
- you are comparing candidate recognition methods

Start with `iaa-task-integration` if:

- the task is mostly config / registry / GUI wiring
- the user wants a placeholder task before real logic exists
- you need to add task settings such as `list[str]` or enable switches
- you are unsure which files must be updated for a new IAA task

Start with `iaa-template-resource-integration` if:

- the user wants a new reusable image template in the repo
- you need to add or edit `resources/**/*.png.json`
- the code should load the image through generated `R.py` resources instead of manual paths
- you are unsure how to turn a probe image into a formal prefab

## Practical Rule

- Real-device reproduction problem: use `kotonebot-emulator-debug`
- Recognition-analysis problem: use `kotonebot-vision-debug`
- New-task integration problem: use `iaa-task-integration`
- New template resource / `R.py` resource flow problem: use `iaa-template-resource-integration`
- End-to-end UI automation bug: use both, in that order
