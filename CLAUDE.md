I am a 3rd year computer engineering student intern and am new to the codebase
# Git and Version Control

For small tasks, avoid creating commits and simply write to the working copy.

For larger tasks, create very small commits as you go. Each commit should have a concise, descriptive commit message. Prefer shorter and more concise to longer, I will ask for a longer commit message if need be.

Never ever add any attribution to commit message. No `Co-Authored-By:` trailers, for any reason (giving attribution to Claude or another user).

Commit messages have a maximum 88-character line length.

# General Coding Practices

## Single-letter variable names

Never use Single-letter variable names. Even in loops and other places, always find a better variable name.

## Comments

### Comment Verbosity

Comments should be 1-3 sentences in length at maximum. If a comment does not provide enough detail I will explicitly ask for more information or a longer comment.

### Use full grammar and punctuation for comments

Always use proper English when writing code comments. For example, rewrite a comment like `# this is not great` to `# This is not great.`.

### Wrap code in backticks (`)

In comments, test code, assert strings and other places, references to code should be wrapped in backticks.

For example, this code block:

```python
# Only return when validate is true.
if validate():
    return True
```

should be re-written like so:

```python
# Only return when `validate` is `True`.
if validate():
    return True
```

### Comments vs Debug logging statements

In contexts with logging, instead of writing comments we should add debug-level log statements. For example, this code:

```python
# Send the request.
requests.get("https://example.com")
```

could instead be written like:

```python
logger.debug("Sending the request.")
requests.get("https://example.com")
```

This allows the code to have clearly labelled sections, and allows us to see detailled logging when increasing the log level to DEBUG.

## Stepdown Readability

Stepdown readability should be used to organize code everywhere is it appropriate.

# Python

## Imports

Always add imports at the beginning of the file. Do not add imports unless absolutely necessary, and if it is necessary, add a comment explaining why the imports cannot be added at the top of the file.

For example, code like this:

```python
import sys

def func():
    from package import blah
    blah()
```

should instead become:

```python
import sys
from package import blah

def func():
    blah()
```

or there should be an explanation:

```python
import sys

def func():
    # Importing blah at the module level causes lazy-loading issues.
    from package import blah
    blah()
```

## Testing `assert` statements

When writing tests with `pytest`, every `assert` statement should include an assert string which describes the test.
This keeps a plain-English description of the intention of the test close to the test itself, and gives better feedback when a test fails.

If you would typically write a comment near the `assert` statement, it should instead be re-written to be the assert statement.

For example, a test like this:

```python
# Check that `method_call` returns `True`.
assert method_call() is True
```

should instead be written like:

```python
assert method_call() is True, "`method_call` should return `True`."
```

## In Python Nothing Is Private

In Python, no function is truly private. I have worked on codebases where there were "private" methods before, and in practice engineers
will simply use the private method since there is nothing stopping them from doign so. Using underscore-prefix to define "private" methods is
silly and makes the code look messy.

Always define methods as public (ie without underscore-prefix) unless explicitly asked to for some reason.

## Count Variables in For-loops

Code like this:

```python
count = 0
for thing in things:
    blah()
    count += 1
```

can always be replaced with `enumerate`:

```python
for count, thing in enumerate(things):
    blah()
```

In general, you should never have to maintain a `count` variable.

## Docstrings Always Have a Single Title Line

The first line of a docstring is always a single line, with an empty line after it.

Bad:

```python
def example():
    """Bug 2004368: a broken `jj` config surfaces the real error, not
    "Not a repository".

    More content.
    """
    ...
```

Good:

```python
def test_jj_broken_config_surfaces_error(monkeypatch, jj_colocated_repo_path, tmp_path):
    """Bug 2004368: a broken `jj` config surfaces the real error, not "Not a repository".

    More content.
    """
    ...
```


# Environment

## Searching

- When searching for code in a given repository, use `rg` to find content of files. Use `fd` to find specific files.
