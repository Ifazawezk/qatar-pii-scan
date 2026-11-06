# qatar-pii-scan

`qpii` looks through code, logs, CSV, Excel and JSON files for personal data in the formats used in Qatar: Qatar ID numbers, +974 phone numbers, Qatar IBANs, emails, passport numbers and names in English or Arabic. It reports where each one is (line and column, CSV row and column, `Sheet!C4`, or a JSON pointer) and never prints a value in full.

It is meant for teams that handle data covered by Qatar's Law No. 13 of 2016 on Protecting Personal Data Privacy (قانون رقم (13) لسنة 2016 بشأن حماية خصوصية البيانات الشخصية). The official Arabic text is on Al Meezan, Qatar's legal portal (almeezan.qa). The tool only finds data. It does not tell you what the law requires and is not a compliance check or legal opinion.

```
$ qpii scan examples/sample/app.log
examples/sample/app.log  line 2, col 46  email     n***@e***.qa                          high
examples/sample/app.log  line 3, col 49  phone     +974 **** **01                        high
examples/sample/app.log  line 4, col 45  passport  *******03                             medium
examples/sample/app.log  line 4, col 72  name      A*** M***                             low
examples/sample/app.log  line 5, col 56  name      ك*** ح***                             low
examples/sample/app.log  line 6, col 42  iban      QA** **** **** **** **** **** ***0 4  high

6 findings in 1 of 1 files: 3 high, 1 medium, 2 low
```

The exit code was 1, because there was at least one medium or high finding.

## Install

```
pip install .
```

Python 3.10+, and openpyxl for Excel files.

## What it finds

| kind | rule | confidence |
|---|---|---|
| Qatar IBAN | `QA`, check digits, 4 letter bank code, 21 characters, MOD 97 check | high, or low if the check digits fail |
| email | the usual shape | high, low for example.com and other reserved domains |
| Qatar ID | 11 digits: 2 or 3, birth year, ISO 3166-1 nationality code, serial | high next to a word like QID or الرقم الشخصي, else medium |
| phone | +974 or 00974 and 8 digits starting with 3, 4, 5, 6 or 7 | high with the country code, medium or low without |
| passport | 1 or 2 letters and 6 to 8 digits, or 8 to 9 digits | medium, only next to "passport" or جواز |
| name | a value in a name column, a title such as Mr. or السيد, or a name with بن or بنت | always low |

Bare 8 digit numbers only count as phones when a word like phone, mobile, هاتف or جوال is on the same line or in the column name, because most 8 digit numbers in code are something else. Arabic-Indic digits (٥٠٠٠٠٠٠١) are read the same as 0-9.

The Qatar ID has no public check digit, so a format match is as far as it goes. The ID and phone rules come from Microsoft Purview's Qatari ID card definition and Qatar's numbering plan filed with the ITU. Name detection is a guess and will miss names and flag some words that are not names; use `--min-confidence medium` to hide it.

## Reports and CI

```
qpii scan . --format sarif -o pii.sarif --html pii.html
```

`--format` is `text`, `json` or `sarif`. `--html` writes a page with a table per file. Every format carries masked values only.

`--fail-on` sets which findings make the exit code 1: `low`, `medium` (default), `high` or `never`. Errors exit with 2. On the sample folder:

```
$ qpii scan examples/sample --format sarif -o pii.sarif --html pii.html
58 findings in 5 of 5 files: 29 high, 7 medium, 22 low
```

To show the findings in GitHub code scanning, upload the SARIF file from a workflow step:

```yaml
- run: pip install . && qpii scan . --format sarif -o pii.sarif --fail-on never
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: pii.sarif
```

The job needs `security-events: write`. SARIF columns are counted in Unicode code points, and Excel and JSON findings carry the cell or pointer as a logical location.

## Allowlist and ignore file

`qpii` reads `.qpiiignore` and `.qpii-allow` from the current folder, or the files you pass with `--ignore-file` and `--allowlist`.

```
# .qpiiignore
tests/fixtures/
*.min.js
docs/**/*.md
```

```
# .qpii-allow
support@company.example
sha256:24531407827f0866decb3e8a4e53ae73fc94a16aad71d9b82d6a5a0e1d6731cf
regex:\+974 4000 \d{4}
kind:name tests/*
```

A plain line is compared without spaces or dashes. If you would rather not keep the value itself in the repo, store its hash; `qpii hash "+974 5000 0001"` prints the line above. `kind:` turns a detector off, everywhere or for matching paths. A line containing `qpii:ignore` is skipped.

## Redact

`qpii redact` writes a masked copy of a CSV, Excel or JSON file and leaves the original alone:

```
$ qpii redact examples/sample/customers.csv -o masked.csv
masked 25 values, wrote masked.csv
$ head -3 masked.csv
id,full_name,الاسم,qid,mobile,email,city
1,N*** A***,ن*** ا***,*********01,******01,n***@e***.qa,Doha
2,K*** H***,ك*** ح***,*********02,+974 **** **02,k***@e***.qa,Doha
```

Excel formulas are left as they are. `--min-confidence medium` keeps names.

## Sample data

`examples/sample` is generated by `python examples/make_samples.py`. All of it is fake but passes the format checks: the IBANs use the bank code FAKE with real MOD 97 check digits, Qatar IDs use serials 00001 to 00999, and emails use example.qa. The helpers in `qatar_pii_scan/fake.py` build the same kind of values for your own tests.

## Limits

This finds data that looks personal; it does not decide whether you may hold it. Treat the output as a list to review, not as legal advice under Law No. 13 of 2016 or any other law. It reads text files, CSV and TSV, `.xlsx` and JSON. Old `.xls`, PDFs, images and files over 20 MB are skipped, and so are `.git`, `node_modules` and virtual environments.

## License

MIT
