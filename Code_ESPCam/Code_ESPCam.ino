#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include "esp_timer.h"
#include <ESPmDNS.h> // <--- 1. THÊM THƯ VIỆN mDNS

// ===================================
// THAY ĐỔI THÔNG TIN WI-FI CỦA BẠN
const char* ssid = "";
const char* password = "";
// ===================================

// Định nghĩa chân cho board AI-THINKER
#define PWDN_GPIO_NUM    32
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM     0
#define SIOD_GPIO_NUM    26
#define SIOC_GPIO_NUM    27
#define Y9_GPIO_NUM      35
#define Y8_GPIO_NUM      34
#define Y7_GPIO_NUM      39
#define Y6_GPIO_NUM      36
#define Y5_GPIO_NUM      21
#define Y4_GPIO_NUM      19
#define Y3_GPIO_NUM      18
#define Y2_GPIO_NUM       5
#define VSYNC_GPIO_NUM   25
#define HREF_GPIO_NUM    23
#define PCLK_GPIO_NUM    22

static httpd_handle_t stream_httpd = NULL;

// Hàm xử lý stream (Giữ nguyên)
static esp_err_t stream_handler(httpd_req_t *req){
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len;
  uint8_t * _jpg_buf;
  char * part_buf[64];
  
  res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=--frame");
  if(res != ESP_OK){
    return res;
  }

  while(true){
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Lỗi chụp ảnh");
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
      
      if(res == ESP_OK){
        res = httpd_resp_send_chunk(req, (const char *)part_buf, sprintf((char *)part_buf, "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", _jpg_buf_len));
      }
      if(res == ESP_OK){
        res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
      }
      if(res == ESP_OK){
        res = httpd_resp_send_chunk(req, "\r\n", 2);
      }
      
      esp_camera_fb_return(fb);
      
      if(res != ESP_OK){
        break;
      }
    }
  }
  return res;
}

void startCameraServer(){
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;

  httpd_uri_t stream_uri = {
    .uri      = "/",
    .method   = HTTP_GET,
    .handler  = stream_handler,
    .user_ctx = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Dùng độ phân giải thấp để Pi xử lý nhanh hơn
  config.frame_size = FRAMESIZE_QVGA; // 320x240 (Mượt hơn VGA)
  config.jpeg_quality = 12; 
  config.fb_count = 2; 
  config.fb_location = CAMERA_FB_IN_PSRAM; 

  // Khởi động camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Khoi dong camera loi: 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_brightness(s, 1); 
  }

  // === BỎ PHẦN CẤU HÌNH IP TĨNH (WiFi.config) ===
  // Để Router tự cấp IP động
  
  // Kết nối Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nDa ket noi WiFi!");

  // === 2. QUAN TRỌNG: ĐẶT TÊN mDNS ===
  // Tên mạng sẽ là: esp32cam.local
  if (MDNS.begin("esp32cam")) { 
    Serial.println("MDNS responder started: esp32cam.local");
  }
  // ==================================

  Serial.print("Stream tai: http://");
  Serial.println(WiFi.localIP()); 

  startCameraServer();
}

void loop() {
  delay(10000);
}
