# Data directory

`data/` chỉ chứa artifact local/seed được phép commit. Đây không phải database hay
data lake production.

## Nội dung

- `catalog.json`: catalog trạng thái và ownership của các miền dữ liệu trong project.
- `gazetteer/place_names.json`: seed địa danh phục vụ demo/normalization, không có
  tọa độ và không được coi là kết quả geocoding đã resolve.
- `app.db`, `chroma/`, model/audio/corpus sinh local nếu có: runtime artifact, phải
  được ignore và không commit nếu chứa PII hoặc dữ liệu chưa được phê duyệt.

## Quy tắc

1. Mọi dataset commit phải có owner, purpose, schema/version, license/provenance và
   xác nhận không chứa secret/PII trái phép.
2. Seed/demo phải tự ghi rõ `DEMO`; không dùng làm production truth.
3. Không commit raw audio, số điện thoại, địa chỉ khách, token hoặc transcript thật.
4. Corpus eval thật cần consent, pseudonymization, retention và access control; lưu
   ngoài Git, chỉ commit manifest/metric đã được duyệt.
5. Khi trạng thái hoặc nguồn runtime đổi, cập nhật `catalog.json` cùng PR.
