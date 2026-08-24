# AloSM Maps Subsystem Architecture (OpenStreetMap Ecosystem)

Tài liệu thiết kế và vận hành subsystem Bản đồ (Maps, Geocoding, Routing) cho AloSM, dựa trên hệ sinh thái **OpenStreetMap (OSM)** mã nguồn mở với **Nominatim** (Geocoding / Reverse Geocoding), **OSRM** (Open Source Routing Machine), và **Leaflet** (Frontend Visualization).

---

## 1. Kiến trúc tổng thể

```text
┌────────────────────────────────────────────────────────┐
│               React Frontend (Vite + TS)               │
│   ├── RideMap (React-Leaflet + OSM TileLayer)          │
│   └── LocationAutocomplete (Debounced Nominatim search)│
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP /api/v1/maps/*
                           ▼
┌────────────────────────────────────────────────────────┐
│                   FastAPI Backend                      │
│   ├── /api/v1/maps/search         (Geocoding)          │
│   ├── /api/v1/maps/reverse        (Reverse Geocode)    │
│   ├── /api/v1/maps/route          (OSRM Routing)       │
│   ├── /api/v1/maps/resolve-trip   (All-in-one trip)    │
│   └── /api/v1/maps/health         (Subsystem health)   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│                     MapsService                        │
│   ├── In-memory / Redis Cache (TTL 1h/5m)              │
│   ├── Service Area Polygon Checker (Hà Nội bounds)     │
│   └── Candidate Session References (Anti-tamper)       │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│      Nominatim Provider      │ │        OSRM Provider         │
│  - Endpoint: /search, /reverse│ │  - Endpoint: /route/v1/      │
│  - User-Agent: AloSM/1.0     │ │  - Coordinate order: lon,lat │
│  - Address normalization     │ │  - Output: GeoJSON LineString│
│  - Bounded retry & backoff   │ │  - Distance (m) & Duration(s)│
└──────────────────────────────┘ └──────────────────────────────┘
               │                          │
               └──────────────┬───────────┘
                              ▼
┌────────────────────────────────────────────────────────┐
│                 Database & Services                    │
│   ├── Places Repository (`places` table)               │
│   ├── Route Snapshots (`route_snapshots` table)        │
│   ├── PricingService (Lộ trình km thật theo OSRM)     │
│   └── LiveKit Voice Agent (Tools: search/route)        │
└────────────────────────────────────────────────────────┘
```

---

## 2. Quy tắc Toạ độ (Coordinate Ordering Rules)

> [!IMPORTANT]
> **OSRM URL format**: `.../{longitude},{latitude};{longitude},{latitude}`.
> **Pydantic API models**: `lat: float`, `lon: float` (`latitude`, `longitude`).
> **GeoJSON format**: `[lon, lat]` bên trong `geometry.coordinates`.
> **Leaflet format**: `[lat, lon]` khi render marker / polyline.

Subsystem đã tự động chuyển đổi chuẩn xác giữa các lớp, đảm bảo không xảy ra lỗi đảo toạ độ.

---

## 3. Danh sách Endpoints API chuẩn

### 3.1. Tìm kiếm địa điểm (Search / Autocomplete)
- **URL**: `GET /api/v1/maps/search` (hoặc `GET /api/maps/search`)
- **Query params**:
  - `q` (string, required): Tên địa điểm, đường phố.
  - `city` (string, optional): Context thành phố (mặc định: `Hà Nội`).
  - `limit` (int, default: 5): Số lượng candidate tối đa.
  - `session_id` (string, optional): Gắn phiên gọi để lưu candidate reference.
- **Response**:
```json
{
  "query": "Bách Khoa",
  "status": "CANDIDATES",
  "results": [
    {
      "id": "osm:998877",
      "name": "Đại học Bách Khoa Hà Nội",
      "display_name": "Đại học Bách Khoa Hà Nội, 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội",
      "lat": 21.0074,
      "lon": 105.8431,
      "address": {
        "road": "1 Đại Cồ Việt",
        "ward": "Bách Khoa",
        "district": "Hai Bà Trưng",
        "city": "Hà Nội",
        "province": "Hà Nội",
        "country": "Việt Nam"
      },
      "provider": "nominatim"
    }
  ]
}
```

### 3.2. Reverse Geocoding (Toạ độ sang địa chỉ)
- **URL**: `GET /api/v1/maps/reverse` (hoặc `GET /api/maps/reverse`)
- **Query params**: `lat`, `lon`, `session_id`

### 3.3. Tính toán lộ trình (Route Calculation)
- **URL**: `POST /api/v1/maps/route` (hoặc `POST /api/maps/route`)
- **Request Body** (Hỗ trợ toạ độ trực tiếp HOẶC place IDs):
```json
{
  "pickup": { "lat": 21.0074, "lon": 105.8431 },
  "destination": { "lat": 21.0285, "lon": 105.8542 },
  "profile": "driving"
}
```
- **Response**:
```json
{
  "route_id": "rte_c08b86e0c65538e1",
  "distance_m": 3500.0,
  "distance_km": 3.5,
  "duration_s": 540.0,
  "duration_minutes": 9,
  "geometry": {
    "type": "LineString",
    "coordinates": [[105.8431, 21.0074], [105.8480, 21.0180], [105.8542, 21.0285]]
  },
  "legs": [...],
  "provider": "osrm"
}
```

### 3.4. Giải quyết toàn bộ chuyến đi (Resolve Trip)
- **URL**: `POST /api/v1/maps/resolve-trip`
- **Request Body**:
```json
{
  "pickup": "Đại học Bách Khoa Hà Nội",
  "destination": "Hồ Hoàn Kiếm",
  "city": "Hà Nội"
}
```
- **Response**: Trả về `pickup` (resolved location), `destination` (resolved location), và `route` (khoảng cách, thời gian, polyline GeoJSON) trong một lượt gọi duy nhất.

### 3.5. Kiểm tra trạng thái Subsystem
- **URL**: `GET /api/v1/maps/health` (hoặc `GET /api/maps/health`)

---

## 4. Frontend Components (React + Leaflet)

1. **`RideMap`** (`src/frontend/src/features/maps/components/RideMap.tsx`):
   - Bản đồ tương tác sử dụng OpenStreetMap tiles miễn phí.
   - Marker Điểm đón (Pin xanh ngọc neon kèm hiệu ứng pulse).
   - Marker Điểm đến (Pin đỏ cam nổi bật).
   - Marker Tài xế di chuyển realtime.
   - Polyline đường đi OSRM với hiệu ứng glow đường viền.
   - Auto `fitBounds` căn chỉnh tự động toàn bộ lộ trình.
   - Huy hiệu thông tin khoảng cách (km) và thời gian (phút) lơ lửng.

2. **`LocationAutocomplete`** (`src/frontend/src/features/maps/components/LocationAutocomplete.tsx`):
   - Ô nhập tìm kiếm địa chỉ với debounce 300ms.
   - Hủy request cũ qua `AbortController` chống race-condition khi gõ nhanh.
   - Dropdown danh sách gợi ý kèm chi tiết địa chỉ phường/quận/thành phố.

---

## 5. Cấu hình Môi trường (.env)

```env
# Maps Provider: "osm" hoặc "openstreetmap"
MAPS_PROVIDER=osm

# Nominatim Geocoding
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
NOMINATIM_USER_AGENT=AloSM/1.0 (ride-hailing; ops@alosm.vn)
NOMINATIM_TIMEOUT_SECONDS=5.0

# OSRM Routing
OSRM_BASE_URL=https://router.project-osrm.org
OSRM_PROFILE=driving
OSRM_TIMEOUT_SECONDS=10.0

# Defaults & Caching
MAP_DEFAULT_CITY=Hà Nội
MAP_DEFAULT_COUNTRY=Vietnam
MAP_SEARCH_LIMIT=5
MAP_CACHE_ENABLED=true
MAP_CACHE_TTL_SECONDS=3600
```
