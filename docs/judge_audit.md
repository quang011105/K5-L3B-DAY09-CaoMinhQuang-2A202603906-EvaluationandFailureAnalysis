# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (PASS) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (FAIL κ, R) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú | Hành động sửa rubric / prompt |
|---|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Xưng 'em' + 'nha', quá suồng sã với khách hàng; judge coi là thân thiện. | Thêm quy tắc cấm xưng 'em' và trợ từ thân mật 'nha' trong văn cảnh CS; bắt buộc đại từ chuẩn mực 'LogiX'. |
| 2 | H-017 | PASS | FAIL | Người đúng | Xưng 'bạn' với khách hàng; judge coi là thân thiện, người đánh giá vi phạm quy chuẩn giao tiếp CS. | Chuẩn hóa danh xưng khách hàng là 'anh/chị' hoặc 'Quý khách'; cấm dùng danh xưng ngang hàng 'bạn'. |
| 3 | H-029 | PASS | FAIL | Người đúng | Giọng ra lệnh ('không cần nhắn thêm'); judge chỉ thấy 'Dạ, vui lòng' nên bỏ sót. | Loại bỏ thiên kiến bắt từ khóa bề mặt 'Dạ, vui lòng'; thêm tiêu chí phát hiện câu mệnh lệnh, gạt bỏ khách hàng. |
| 4 | H-042 | FAIL | PASS | Người đúng | Ngắn gọn nhưng đầy đủ số tiền và thời hạn 3–5 ngày; judge phạt máy móc vì 'thiếu xin lỗi'. | Nới lỏng rubric: không bắt buộc xin lỗi khi yêu cầu đã được giải quyết thỏa đáng, ưu tiên tính rõ ràng của thông tin hoàn tiền. |
| 5 | HL-016 | PASS | FAIL | Người đúng | Câu văn xin lỗi lịch sự chuẩn mực nhưng báo sai tiền (55.000đ vs ledger 35.000đ); judge không đối chiếu ledger nên bỏ sót lỗi nghiêm trọng. | Loại bỏ hoàn toàn LLM judge đối với tiêu chí `helpful` có dính dáng tới số liệu; bắt buộc dùng code grader (`ReplyMatchesLedger`) so khớp trực tiếp với ledger SQLite. |

## Kết luận
- **Tiêu chí bị loại và lý do**: 
  - Tiêu chí `helpful` bị loại vì ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` có FN=21 (bỏ sót 70% số lỗi thực tế, Recall=0.300 < 0.7) và κ=0.375 (< 0.6). LLM judge bị halo effect bởi những câu xin lỗi hoa mỹ và boilerplate văn phong mà hoàn toàn bất lực trong việc phát hiện sai lệch số tiền và thực tế nghiệp vụ.
  - Tiêu chí `tone_ok` được chấp nhận sử dụng vì vượt qua toàn bộ các ngưỡng khắt khe (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7).
  - Khẳng định nguyên tắc thiết kế: Tiền bạc và approval phải luôn được chấm bằng code grader tất định, tuyệt đối không giao cho LLM judge.
- **Rủi ro còn lại**: 
  - Judge chỉ được kiểm trên tập dữ liệu replay đã công khai (judge_tone_public.csv); cần thu thập nhãn chuyên gia mới theo định kỳ để có held-out test thật nhằm phát hiện prompt drift và judge degradation.
