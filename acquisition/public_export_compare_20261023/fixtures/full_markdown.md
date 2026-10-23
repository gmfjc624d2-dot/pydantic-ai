![Example research logo](https://example.org/static/logo.png)

# Which conditions apply before running the export check? Request ID: req-20261023-0001

Run only if the source is verified[^1]. Do not infer permission from a successful read[^2].


The check runs 3 times before it reports a result[^1]. Examples in C\# follow the same rule[^3].

| Step | Condition | Limit |
| --- | --- | --- |
| Read | source verified[^1] | 3 attempts |
| Write | explicit permission[^2] | 0 attempts |

Keep the literal markers in this snippet unchanged:

```python
refs = ["[1]", "[^1]", "\\#"]
print(refs[1])
```

    indented note: notes[2] and C\# stay literal

1. Verify the source[^1].
2. Record the permission decision[^2].

Caveat: a successful read is not permission[^2]. See https://example.org/faq?q=a[1]&lang=en for the query form.

[^1]: https://example.org/guide/verify?version=1
[^2]: https://example.org/permissions#read
[^3]: https://example.org/languages/csharp

<span style="display:none">[^4]: https://example.org/archive/background
[^5]: https://example.org/archive/unlisted</span>
