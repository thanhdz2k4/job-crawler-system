# Giải pháp Rate Limiting cho Job Crawler System

## Vấn đề

Khi chạy crawler, bạn gặp lỗi `WARNING: Rate limited (429)` từ Airflow. Đây là lỗi xảy ra khi hệ thống gửi quá nhiều yêu cầu đến website trong khoảng thời gian ngắn, khiến website chặn truy cập.

## Nguyên nhân chính

1. **Xung đột cấu hình**: Spider định nghĩa `DOWNLOAD_DELAY=2` và `CONCURRENT_REQUESTS=8`, nhưng settings.py lại định nghĩa `DOWNLOAD_DELAY=15` và `CONCURRENT_REQUESTS=1`.
2. **Cấu hình spider override settings**: Cấu hình trong spider sẽ override cấu hình global, dẫn đến việc gửi 8 request đồng thời với delay chỉ 2 giây.
3. **Thiếu cơ chế backoff thông minh**: Khi bị rate limit, hệ thống không có cơ chế xử lý phù hợp.

## Giải pháp đã triển khai

### 1. Cấu hình tập trung

Tạo file `config/rate_limiting.yaml` để quản lý tất cả cấu hình rate limiting:

```yaml
# Global rate limiting settings
global:
  download_delay: 20
  randomize_download_delay: true
  concurrent_requests: 1
  concurrent_requests_per_domain: 1

# AutoThrottle settings
autothrottle:
  enabled: true
  start_delay: 20
  max_delay: 180
  target_concurrency: 0.2
  debug: true

# Domain-specific settings
domains:
  topcv.vn:
    download_delay: 25
    max_delay: 300
    concurrent_requests: 1
    max_pages_per_run: 5
```

### 2. Module quản lý cấu hình

Tạo `config/rate_limiting_config.py` để:
- Load cấu hình từ YAML file
- Cung cấp interface để truy cập các thiết lập
- Hỗ trợ domain-specific settings
- Tự động generate Scrapy settings

### 3. Cải thiện RateLimitMiddleware

Nâng cấp `src/crawlers/common/rate_limit_middleware.py` với:
- Exponential backoff thông minh
- Domain-specific tracking
- Jitter để tránh synchronized retries
- Penalty cho các domain thường bị rate limit

### 4. Cập nhật cấu hình Scrapy

- Loại bỏ xung đột giữa spider và global settings
- Sử dụng cấu hình từ rate_limiting_config
- Tăng delay và giảm concurrent requests

### 5. Cập nhật Airflow DAG

- Giảm số trang mặc định từ 10 xuống 5
- Tăng timeout để accommodate longer delays
- Sử dụng rate limiting settings từ config

## Cách sử dụng

### 1. Kiểm tra cấu hình hiện tại

```python
from config.rate_limiting_config import get_scrapy_settings, get_domain_settings

# Lấy tất cả settings cho Scrapy
settings = get_scrapy_settings('topcv.vn')
print(settings)

# Lấy settings cho domain cụ thể
domain_settings = get_domain_settings('topcv.vn')
print(domain_settings)
```

### 2. Chạy crawler với rate limiting

```bash
# Chạy với cấu hình mặc định
scrapy crawl topcv_spider

# Chạy với số trang giới hạn
scrapy crawl topcv_spider -a max_pages=3

# Override delay nếu cần
scrapy crawl topcv_spider -s DOWNLOAD_DELAY=30
```

### 3. Tùy chỉnh cấu hình

Chỉnh sửa file `config/rate_limiting.yaml`:

```yaml
# Tăng delay cho TopCV
domains:
  topcv.vn:
    download_delay: 30  # Tăng từ 25 lên 30
    max_pages_per_run: 3  # Giảm từ 5 xuống 3
```

### 4. Monitor và debug

Kích hoạt debug mode:

```yaml
autothrottle:
  debug: true  # Log thông tin throttle
```

Kiểm tra logs cho các thông báo:
- `🚫 Rate limited (429)` - Khi bị rate limit
- `RateLimitMiddleware stats` - Thống kê khi spider đóng
- `Domain-specific rate limiting stats` - Thống kê theo domain

## Best Practices

### 1. Start conservative

Bắt đầu với delay cao và concurrent requests thấp, sau đó điều chỉnh dần.

### 2. Use AutoThrottle

Luôn bật AutoThrottle để tự động điều chỉnh tốc độ dựa trên response time.

### 3. Monitor regularly

Kiểm tra logs thường xuyên để phát hiện sớm các vấn đề rate limiting.

### 4. Domain-specific settings

Sử dụng cấu hình riêng cho mỗi domain vì mỗi website có giới hạn khác nhau.

### 5. Exponential backoff

Sử dụng exponential backoff với jitter để tránh thundering herd problem.

## Troubleshooting

### Vẫn bị rate limit?

1. **Tăng DOWNLOAD_DELAY**: Thử tăng lên 30-60 giây
2. **Giảm CONCURRENT_REQUESTS**: Đảm bảo là 1
3. **Giảm max_pages_per_run**: Crawl ít trang hơn mỗi lần chạy
4. **Sử dụng proxy**: Cân nhắc sử dụng proxy rotation

### Crawler quá chậm?

1. **Kiểm tra AutoThrottle**: Đảm bảo `target_concurrency` không quá thấp
2. **Optimize parsing**: Giảm thời gian xử lý mỗi page
3. **Parallel processing**: Xem xét xử lý song song các công đoạn khác nhau

### Logs không hiển thị?

1. **Kiểm tra LOG_LEVEL**: Đặt thành `DEBUG` để xem chi tiết
2. **Enable AUTOTHROTTLE_DEBUG**: Để xem thông tin throttle
3. **Check middleware logs**: Đảm bảo middleware được load đúng

## File đã thay đổi

1. `src/crawlers/topcv/spider.py` - Loại bỏ custom_settings
2. `src/crawlers/settings.py` - Sử dụng rate_limiting_config
3. `src/crawlers/common/rate_limit_middleware.py` - Nâng cấp middleware
4. `dags/job_crawler_dag.py` - Sử dụng rate limiting config
5. `config/rate_limiting.yaml` - File cấu hình mới
6. `config/rate_limiting_config.py` - Module quản lý cấu hình mới

## Kết quả

Sau khi áp dụng các thay đổi này:
- Giảm đáng kể các lỗi rate limiting (429)
- Crawler hoạt động ổn định hơn
- Dễ dàng tùy chỉnh và monitor
- Hỗ trợ nhiều domain với cấu hình riêng biệt
- Tự động điều chỉnh tốc độ dựa trên response của server