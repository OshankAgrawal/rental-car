from prediction import predict_image

image_path = "E:\Rental-Car-Project\WhatsApp Video 2026-11-23 at 2.28.57 PM.mp4"

result = predict_image(image_path)

print("\nDamage Detection Results")
print("------------------------")

print("Total detections:", result["total_detections"])

for detection in result["detections"]:

    print("\nDamage:", detection["damage_type"])
    print("Confidence:", detection["confidence"])
    print("Bounding Box:", detection["bbox_xyxy"])