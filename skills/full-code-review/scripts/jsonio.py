"""JSON file helpers shared by the review scripts."""
import json
import os
import tempfile


def write_json(path, value):
    """Write `value` as sorted, indented JSON to `path`, replacing it atomically.

    Creates missing parent directories. The data is fsynced before the rename, and the
    temp file is unique per call so concurrent writers never share one.
    """
    target = os.path.abspath(str(path))
    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".%s." % os.path.basename(target), suffix=".tmp",
                                dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, target)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def load_object(path, label="JSON input"):
    """Return the JSON object stored at `path`.

    Raises ValueError naming `label` when the file is unreadable, is not valid JSON, or
    holds anything other than an object.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("could not read %s: %s" % (label, exc))
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % label)
    return value
