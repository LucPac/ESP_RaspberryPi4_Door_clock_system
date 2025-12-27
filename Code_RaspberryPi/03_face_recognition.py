import cv2
import numpy as np
import os
import paho.mqtt.client as mqtt # Dùng lại thư viện MQTT
import time

# ----------------------------------------------------
#               CÀI ĐẶT CƠ BẢN (Giữ nguyên)
# ----------------------------------------------------
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read('trainer/trainer.yml')
cascadePath = "haarcascade_frontalface_default.xml"
faceCascade = cv2.CascadeClassifier(cascadePath);
font = cv2.FONT_HERSHEY_SIMPLEX
names = ['None', 'Dat', 'Duong'] # Đảm bảo ID 1=Dat, ID 2=Duong

# ----------------------------------------------------
#               CÀI ĐẶT MQTT (PHIÊN BẢN SỬA LỖI)
# ----------------------------------------------------
BROKER_IP = "192.168.1.9" # IP của chính Pi
MQTT_TOPIC_OPEN = "cua/lenh_mo" # Topic để mở cửa
MQTT_TOPIC_WARNING = "canh_bao/nguoi_la" # <-- TOPIC MỚI CHO CẢNH BÁO

# === HÀM SỬA LỖI: ĐÚNG 5 THAM SỐ ===
def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
	print(f"!!! Phat hien mat ket noi MQTT, code={reason_code}")

def on_connect(client, userdata, flags, rc, properties=None): # Thêm properties cho V2
	if rc == 0:
		print("Da ket noi MQTT Broker!")
	else:
		print(f"Ket noi loi, code={rc}")

# Khởi tạo MQTT client (V2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# === SỬA LỖI KẾT NỐI: DÙNG KEEPALIVE 10 GIÂY ===
try:
	client.connect(BROKER_IP, 1883, 10) # 10 giây (thay vì 60)
	print("Dang ket noi MQTT...")
except Exception as e:
	print(f"Loi: Khong the ket noi Broker MQTT tai {BROKER_IP}. {e}")
	print("Ban da chay server Mosquitto chua?")
	exit()

client.loop_start() # Bắt đầu vòng lặp chạy nền

# Biến để làm cooldown (Giữ nguyên)
last_signal_time = 0
COOLDOWN_SECONDS = 5 # Chờ 5 giây

# === BIẾN MỚI: ĐỂ THEO DÕI "UNKNOWN" ===
unknown_start_time = 0 			# Thời điểm bắt đầu thấy người lạ
UNKNOWN_DURATION = 5 			# Thời gian (giây) phát hiện "unknown" để gửi cảnh báo
is_tracking_unknown = False 	# Cờ báo là đang theo dõi người lạ
last_warning_signal_time = 0 	# Cooldown cho tin nhắn cảnh báo (5 giây)

# ----------------------------------------------------
#               CÀI ĐẶT CAMERA (Giữ nguyên)
# ----------------------------------------------------
cam_url = "http://192.168.1.100"
cam = cv2.VideoCapture(cam_url)
cam.set(3, 640)
cam.set(4, 480)
minW = 0.1*cam.get(3)
minH = 0.1*cam.get(4)

# ----------------------------------------------------
#               VÒNG LẶP CHÍNH (ĐÃ SỬA LOGIC)
# ----------------------------------------------------
while True:
	ret, img =cam.read()

	if not ret:
		print("Loi stream, dang ket noi lai...")
		cam.release()
		cam = cv2.VideoCapture(cam_url)
		time.sleep(2)
		continue

	gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

	faces = faceCascade.detectMultiScale(
		gray,
		scaleFactor = 1.2,
		minNeighbors = 5,
		minSize = (int(minW), int(minH)),
		)

	# --- Logic mới (Phần 1): Quét tất cả các khuôn mặt ---

	found_known_face = False
	found_unknown_face = False

	# Mảng để lưu thông tin vẽ lên màn hình (tránh vẽ và xử lý logic lẫn lộn)
	faces_to_draw = []
	id_name = "" # Reset id_name mỗi khung hình

	for(x,y,w,h) in faces:
		id, confidence = recognizer.predict(gray[y:y+h,x:x+w])

		# In ra để debug (bạn đã có)
		# print(f"  -> Da phat hien 1 khuon mat. ID: {id}, Confidence: {confidence}")

		if (confidence < 100):
			id_name = names[id]
			confidence_text = "  {0}%".format(round(100 - confidence))
			found_known_face = True
		else:
			id_name = "unknown"
			confidence_text = "  {0}%".format(round(100 - confidence))
			found_unknown_face = True

		# Thêm thông tin để vẽ sau
		faces_to_draw.append((x, y, w, h, id_name, confidence_text))


	# --- Logic mới (Phần 2): Quyết định hành động (Publish) ---

	current_time = time.time()

	if found_known_face:
		# 1. TÌM THẤY NGƯỜI QUEN: Mở cửa và reset timer "unknown"
		is_tracking_unknown = False # Dừng theo dõi người lạ

		# Chỉ gửi lệnh "OPEN" nếu đủ cooldown
		if current_time - last_signal_time > COOLDOWN_SECONDS:
			try:
				# (Dùng id_name cuối cùng được phát hiện)
				print(f"Nhan dien: {id_name}. Dang PUBLISH (qos=1)...")
				if not client.is_connected():
					client.reconnect()
				client.publish(MQTT_TOPIC_OPEN, "OPEN", qos=1) # Gửi lệnh MỞ
				print("   -> Publish thanh cong (Broker da xac nhan).")
				last_signal_time = current_time
			except Exception as e:
				print(f"!!! Loi publish (OPEN): {e}")

	elif found_unknown_face:
		# 2. CHỈ THẤY NGƯỜI LẠ (Không thấy người quen)
		if not is_tracking_unknown:
			# Lần đầu tiên thấy, bắt đầu đếm
			print("Phat hien NGUOI LA. Bat dau dem 5 giay...")
			is_tracking_unknown = True
			unknown_start_time = current_time
		else:
			# Đang theo dõi, kiểm tra thời gian
			time_elapsed = current_time - unknown_start_time
			print(f"Nguoi la van con day... ({time_elapsed:.1f}s / {UNKNOWN_DURATION}s)")

			if time_elapsed > UNKNOWN_DURATION:
				# Đã đủ 5 giây, gửi cảnh báo
				if current_time - last_warning_signal_time > COOLDOWN_SECONDS:
					try:
						print(f"NGUOI LA da o day {UNKNOWN_DURATION} giay! Dang PUBLISH canh bao...")
						if not client.is_connected():
							client.reconnect()
						# Gửi cảnh báo
						client.publish(MQTT_TOPIC_WARNING, "UNKNOWN_DETECTED", qos=1)
						print("   -> Canh bao da gui (Broker xac nhan).")

						last_warning_signal_time = current_time
						is_tracking_unknown = False # Reset lại để đếm lại từ đầu

					except Exception as e:
						print(f"!!! Loi khi publish canh bao: {e}")
	else:
		# 3. KHÔNG THẤY AI CẢ
		if is_tracking_unknown:
			print("Nguoi la da roi di. Reset bo dem.")
		is_tracking_unknown = False # Reset bộ đếm


	# --- Logic cũ (Phần 3): Vẽ lên màn hình ---
	# (Tách riêng để không ảnh hưởng logic)
	for (x, y, w, h, id_name, confidence_text) in faces_to_draw:
		cv2.rectangle(img, (x,y), (x+w,y+h), (0,255,0), 2)
		cv2.putText(img, str(id_name), (x+5,y-5), font, 1, (255,255,255), 2)
		cv2.putText(img, str(confidence_text), (x+5,y+h-5), font, 1, (255,255,0), 1)

	# cv2.imshow('camera',img) # Bỏ comment nếu bạn muốn xem
	# k = cv2.waitKey(10) & 0xff
	# if k == 27:
	#     break

# ----------------------------------------------------
#               DỌN DẸP
# ----------------------------------------------------
print("\n [INFO] Exiting Program and cleanup stuff")
client.loop_stop() # Dừng vòng lặp MQTT
client.disconnect() # Ngắt kết nối
cam.release()
# cv2.destroyAllWindows()
