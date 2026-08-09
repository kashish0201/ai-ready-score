# CSV Upload Limit Design

## Goal

Reject CSV uploads larger than 200 MB before pandas parses them, preventing excessive memory use and returning a clear API error.

## Scope

This change applies only to `POST /api/datasets`. Existing CSV parsing, validation, dataset storage, and frontend behavior remain unchanged.

## Design

- Define a 200 MB limit in bytes in `backend/main.py`.
- Check `UploadFile.size` before calling `file.read()`.
- If the framework does not provide a size, seek to the end of the spooled upload, read its position, and rewind to the beginning.
- If the measured size is greater than 200 MB, raise `HTTPException` with status `413 Payload Too Large` and a message stating the limit.
- Files exactly 200 MB remain valid and continue to the existing CSV parsing flow.

FastAPI/Starlette already spools multipart uploads. Measuring the upload before reading it into application bytes avoids handing oversized content to pandas while keeping the implementation small.

## Error Response

Oversized files return:

```json
{
  "detail": "CSV file exceeds the 200 MB upload limit"
}
```

## Testing

- A file whose reported size is greater than 200 MB returns 413 without invoking CSV parsing.
- A file exactly 200 MB is not rejected by the size guard.
- Existing empty, malformed, and valid CSV tests continue to pass.
