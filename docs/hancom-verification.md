# 한컴오피스 열림 검증 체크리스트 (Phase 2 게이트)

base 템플릿은 OWPML 스펙 기반 클린룸 작성물로, 구조 검증(validate)은
통과하지만 실제 한컴오피스 열림은 아직 확인되지 않았다. 아래를 한컴이
설치된 환경에서 1회 수행한다.

## 검증 절차

1. `python3 scripts/hwpx.py new samples/verify.md -o verify.hwpx` 로 생성
   (samples/verify.md: 제목 + 본문 + 불릿 + 순서목록 + 3x2 표를 포함할 것)
2. 한컴오피스(한글)에서 verify.hwpx를 연다.
3. 확인 항목:
   - [ ] 경고/복구 대화상자 없이 열리는가
   - [ ] 제목이 18pt 굵은 돋움으로 보이는가
   - [ ] 본문이 10pt 바탕, 양쪽 정렬로 보이는가
   - [ ] 표의 테두리와 헤더 행 회색 배경이 보이는가
   - [ ] 편집(타이핑) 후 저장이 정상 동작하는가
4. 편집 후 저장한 파일을 `python3 scripts/hwpx.py validate`로 재검증한다.

## 실패 시

- 대화상자 문구/증상을 기록해 이슈로 남긴다.
- 한컴에서 빈 문서를 .hwpx로 저장한 파일을 확보하면:
  unpack으로 header.xml/section0.xml 구조를 비교하고, 차이를
  scripts/dev/gen_base_template.py에 반영하거나, 스펙 §8의 헤지대로
  한컴 저장본을 새 base 템플릿으로 채택한다 (secPr 추출 구조라
  코드 변경 불필요).
