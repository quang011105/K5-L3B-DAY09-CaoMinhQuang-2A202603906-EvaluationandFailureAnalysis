# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-560a` |
| Triệu chứng | Grader fail: `status resolved != denied`, `refund_amount_correct` fail (ledger=20000 != label=0), `db_fact_kept` fail. Reply nói "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." trong khi đơn giao trễ 1 ngày không đủ điều kiện hoàn tiền (nhãn: 0đ, denied). |
| Bước sai đầu tiên | Event 3: `model_override` + payload `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) đúng hợp đồng `handoff.v1`; Event 2 (`investigator`) chạy công cụ `lookup_order` đọc đúng thực tế DB của đơn O-202 là `delay_days: 1`. Toàn bộ dữ liệu trước Event 3 hoàn toàn chính xác. |
| Failure mode | FM-03 (`ticket_trust`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim `C-002@11` trên shape `fixed`: Event 2 đọc DB `delay_days: 1`; Event 3 sinh quote 0đ (`no_entitlement`), Event 4 trả lời từ chối đúng chính sách, ledger ghi 0đ, pass toàn bộ graders. |
| Regression test | Evaluator `DbFactKept` trong `src/lab9/graders.py` + test `test_override_event_breaks_db_fact` trong `tests/test_lab9_graders.py`; đã xác nhận fail trên `seeded_regression` và pass trên `fixed`. |
| Chưa chắc chắn | Trace chứng minh rõ event `model_override` do telemetry bắt được, nhưng không cho thấy được cơ chế chú ý (attention weight) bên trong LLM thực sự đã bị thiên kiến bởi cụm từ nào trong ticket nếu chạy model đen không có hook. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
