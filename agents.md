# Agent Rules for JiraSee Development

## Code Quality Standards
* Always write code with a clear separation of concerns
* Keep code simple and easy to maintain
* Always write unit tests for new code and update tests for updated code
* Aim for 80% unit test coverage and above
* Always run all tests and fix all issues before finishing a task
* always fix issues even if you did not introduce them
* Always include code formatting and type checking along with unit tests. Use ruff to check code formatting and mypy to check types
* Use modern python capabilities like pydantic and protocol classes for interfaces etc.
* Keep business log separated
* keep domain logic separated
* use modern python coding practicces, for example always use pydantic and dont create raw dicts. When possible dict content should not be raw strings
* use Enums instead of related constants at a module level
* when creating code that is used as an interface in python use Protocol
* never use inline imports always place imports at the top of a file
* never implement fallback code for missing imports unless necessary for running under different operating systems

## Progress Documentation
* **When completing a phase of implementation**, write progress information to the phase-specific progress file (e.g., `progress/phase4_progress.md`)
* **Each phase has its own progress file** in the format `progress/phaseN_progress.md`
* Include information about what has been done and why, design and architecture decisions, bug fixes, and metrics
* The target audience for progress documentation is future developers who will need to pick up from work that has previously been completed
* keep the information in all progress documentation short, terse, and accurate
* Always update the main `progress/progress.md` file to reflect the current status
* always add date and time indicators to progress updates
* keep progress updates and information current, it should be a reference to what has recently happened to the codebase.
* when removing old progress information from progress documents, copy it into a new file with a date and timestamp and put the new file in a folder called progres/archived/

## Reading Progress Documentation
* **When investigating the codebase**, start with `progress/progress.md` to see the overall project status and links to phase files
* **Read the most recent phase progress file first** (e.g., `progress/phase4_progress.md` for the most recently completed phase)
* **Only refer to previous phase progress files** if you need to do work that affects features implemented in those earlier phases
* This approach keeps context focused and avoids loading unnecessary historical information

## User Documentation
* Always make sure to create and update documentation in the `documentation/` folder
* The target audience for this documentation is the end users of the application
* Keep user documentation separate from developer progress documentation

## Development Tools
* Always use the python `uv` tool for managing dependencies and python virtual environments
* Use ruff for code formatting and linting
* Use mypy for type checking
* Use pytest for testing

## Planning and Implementation
* For new implementation work, always refer to information in the `planning/` folder to understand the plan and implementation steps for the project
* Always keep the `planning/phased_acceptance_tests.md` document up to date with the current status of the implementation so the expected results stated for each test are correct considering the current status of the implementation
* Always double check the names used in the code for classes, attributes, variables, methods, functions, names, properties etc.. are correct and consistent within the code to avoid mismatching name errors.

## Logging
* Always implement structured, comprehensive, detailed DEBUG level logging to help when developing the application
* DEBUG logging should go to STDOUT and a file in a `logs/` folder

## Adhoc Scripts
* If you create any adhoc or temporary scripts, or scripts or programs to test things while working on implementation or investigating issues, outside of unit tests, always create them in the `adhoc_scripts/` folder

## accessing local infrastructure

 - there is a kubernetes cluster whose control plane is hosted on pi1
 - passwordless access is setup for user matt to hosts pi1, pi2 and pi3
 - a host called 'server' is available. You must use the exec_ssh tool to run commands on host 'server'
 - host 'server' an the apache web server. All inbound http and https connections to 'dgen.uk' will resolve to the host 'server' and be proxied by the apache webserver to the ingress controller endpoint in the kubernetes cluster
 - the ingress controller is intended to route to applications in the cluster using the first part of the URL path in the request and then strip the first part of the path from the url so applications in the cluster can operate as if they were mounted at '/'

 - when using ssh commands directly with passwordless access, always use the ip addresses for the hosts as follows:-

 pi1   192.168.1.101
 pi2   192.168.1.103
 pi3   192.168.1.105


 -  As mentioned above, to run ssh commands on host 'server' you MUST use the ssh_exec tool with the host 'server'

 - You can run kubectl commands on host pi1 to manage the kubernetes cluster