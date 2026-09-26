# Sample inputs

Each demo has a required `data` upload. Drop one of these into it so you can
actually submit the form:

| File | Use it for |
|---|---|
| `measurements.csv` | 12 rows of dose/response data; the demos report its row count |
| `notes.txt` | a non-CSV file, to see that the original extension survives the upload |

The upload is written to a private temporary directory under its **original**
name, so the function receives a real, readable `Path` whose `.name` is the file
you picked -- not a randomised temp name.
