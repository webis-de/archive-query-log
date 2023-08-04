id_ suffix to get the raw html
x-archie-src header to get the source WARC file
not all CDX APIs support  showResumeKey=true -> detect if last line is preceded by a blank line



Query ?url=PREFIX&matchType=prefix&fl=url,original,timestamp&output=text&limit=1&showResumeKey=true
- If last line is preceded by a blank line, use resumeKey for pagination, else don't use pagination.
- If first line has 3 columns (whitespace-separated), use fl=url,timestamp
2. Query ?url=PREFIX&matchType=prefix&fl=url,original,timestamp&output=text&limit=1&showNumPages=true
    If contains single number, use pages for pagination
