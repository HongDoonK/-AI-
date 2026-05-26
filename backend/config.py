# config.py
# ──────────────────────────────────────────────────────────────
# 컬럼명을 여기에만 모아두는 파일
# AI 담당자와 합의 후 컬럼명이 바뀌면
# 1단계 상수값만 수정하면 아래 모든 곳에 자동 반영됨
# ──────────────────────────────────────────────────────────────


# ════════════════════════════════════════════════════════════════
# 1단계: 실제 DB 컬럼명을 상수로 정의
# AI 담당자와 합의 후 여기만 수정하면 됨
# ════════════════════════════════════════════════════════════════

# policies 테이블 컬럼명
COL_POLICY_ID           = "policy_id"           # 정책번호
COL_POLICY_NAME         = "policy_name"         # 정책명
COL_KEYWORD             = "keyword"             # 정책키워드명
COL_DESCRIPTION         = "description"         # 정책설명내용
COL_CATEGORY_MAIN       = "category_main"       # 정책대분류명
COL_CATEGORY_SUB        = "category_sub"        # 정책중분류명
COL_SUPPORT_CONTENT     = "support_content"     # 정책지원내용
COL_PVSN_METHOD         = "pvsn_method"         # 정책제공방법코드
COL_INSTITUTION         = "institution"         # 주관기관코드명
COL_INSTITUTION_MANAGER = "institution_manager" # 주관기관담당자명
COL_OPER_INST           = "oper_inst"           # 운영기관코드명
COL_SUPPORT_SCALE       = "support_scale"       # 지원규모수
COL_ARRIVE_SEQ          = "arrive_seq"          # 지원도착순서여부
COL_APPLY_PERIOD_TYPE   = "apply_period_type"   # 신청기간구분코드
COL_BIZ_PERIOD_TYPE     = "biz_period_type"     # 사업기간구분코드
COL_BIZ_START_DATE      = "biz_start_date"      # 사업기간시작일자
COL_BIZ_END_DATE        = "biz_end_date"        # 사업기간종료일자
COL_BIZ_PERIOD_ETC      = "biz_period_etc"      # 사업기간기타내용
COL_APPLY_METHOD        = "apply_method"        # 정책신청방법내용
COL_SELECTION_METHOD    = "selection_method"    # 심사방법내용
COL_APPLICATION_URL     = "application_url"     # 신청URL주소
COL_SUBMIT_DOCS         = "submit_docs"         # 제출서류내용
COL_ETC                 = "etc"                 # 기타사항내용
COL_REF_URL1            = "ref_url1"            # 참고URL주소1
COL_REF_URL2            = "ref_url2"            # 참고URL주소2
COL_APPLY_PERIOD        = "apply_period"        # 신청기간
COL_MIN_AGE             = "min_age"             # 지원대상최소연령
COL_MAX_AGE             = "max_age"             # 지원대상최대연령
COL_AGE_LIMIT           = "age_limit"           # 지원대상연령제한여부
COL_MARRIAGE_STATUS     = "marriage_status"     # 결혼상태코드
COL_INCOME_TYPE         = "income_type"         # 소득조건구분코드
COL_INCOME_MIN          = "income_min"          # 소득최소금액
COL_INCOME_MAX          = "income_max"          # 소득최대금액
COL_INCOME_ETC          = "income_etc"          # 소득기타내용
COL_APPLY_CONDITION     = "apply_condition"     # 추가신청자격조건내용
COL_EXCLUDED_TARGET     = "excluded_target"     # 참여제한대상내용
COL_REGION              = "region"              # 정책거주지역코드
COL_MAJOR_CD            = "major_cd"            # 정책전공요건코드
COL_JOB_CD              = "job_cd"              # 정책취업요건코드
COL_SCHOOL_CD           = "school_cd"           # 정책학력요건코드
COL_SPECIAL_CD          = "special_cd"          # 정책특화요건코드
COL_FIRST_REG_DATE      = "first_reg_date"      # 최초등록일시
COL_LAST_MOD_DATE       = "last_mod_date"       # 최종수정일시
COL_SEARCH_TEXT         = "search_text"         # 임베딩용 통합텍스트 (자동생성)

# centers 테이블 컬럼명
COL_CENTER_ID           = "center_id"           # 센터일련번호
COL_CENTER_NAME         = "center_name"         # 센터명
COL_CENTER_TEL          = "center_tel"          # 센터전화번호
COL_CENTER_ADDR         = "center_addr"         # 센터주소
COL_CENTER_DADDR        = "center_daddr"        # 센터상세주소
COL_CENTER_URL          = "center_url"          # 센터URL주소
COL_CENTER_CTPV_CD      = "center_ctpv_cd"      # 법정동시도코드
COL_CENTER_CTPV_NM      = "center_ctpv_nm"      # 법정동시도코드명
COL_CENTER_SGG_CD       = "center_sgg_cd"       # 법정동시군구코드
COL_CENTER_SGG_NM       = "center_sgg_nm"       # 법정동시군구코드명


# ════════════════════════════════════════════════════════════════
# 2단계: 위 상수를 참조해서 딕셔너리 구성
# 여기는 수정하지 않아도 됨
# ════════════════════════════════════════════════════════════════

POLICY_COLUMNS = {
    "policy_id":           COL_POLICY_ID,
    "policy_name":         COL_POLICY_NAME,
    "keyword":             COL_KEYWORD,
    "description":         COL_DESCRIPTION,
    "category_main":       COL_CATEGORY_MAIN,
    "category_sub":        COL_CATEGORY_SUB,
    "support_content":     COL_SUPPORT_CONTENT,
    "pvsn_method":         COL_PVSN_METHOD,
    "institution":         COL_INSTITUTION,
    "institution_manager": COL_INSTITUTION_MANAGER,
    "oper_inst":           COL_OPER_INST,
    "support_scale":       COL_SUPPORT_SCALE,
    "arrive_seq":          COL_ARRIVE_SEQ,
    "apply_period_type":   COL_APPLY_PERIOD_TYPE,
    "biz_period_type":     COL_BIZ_PERIOD_TYPE,
    "biz_start_date":      COL_BIZ_START_DATE,
    "biz_end_date":        COL_BIZ_END_DATE,
    "biz_period_etc":      COL_BIZ_PERIOD_ETC,
    "apply_method":        COL_APPLY_METHOD,
    "selection_method":    COL_SELECTION_METHOD,
    "application_url":     COL_APPLICATION_URL,
    "submit_docs":         COL_SUBMIT_DOCS,
    "etc":                 COL_ETC,
    "ref_url1":            COL_REF_URL1,
    "ref_url2":            COL_REF_URL2,
    "apply_period":        COL_APPLY_PERIOD,
    "min_age":             COL_MIN_AGE,
    "max_age":             COL_MAX_AGE,
    "age_limit":           COL_AGE_LIMIT,
    "marriage_status":     COL_MARRIAGE_STATUS,
    "income_type":         COL_INCOME_TYPE,
    "income_min":          COL_INCOME_MIN,
    "income_max":          COL_INCOME_MAX,
    "income_etc":          COL_INCOME_ETC,
    "apply_condition":     COL_APPLY_CONDITION,
    "excluded_target":     COL_EXCLUDED_TARGET,
    "region":              COL_REGION,
    "major_cd":            COL_MAJOR_CD,
    "job_cd":              COL_JOB_CD,
    "school_cd":           COL_SCHOOL_CD,
    "special_cd":          COL_SPECIAL_CD,
    "first_reg_date":      COL_FIRST_REG_DATE,
    "last_mod_date":       COL_LAST_MOD_DATE,
    "search_text":         COL_SEARCH_TEXT,
}

CENTER_COLUMNS = {
    "center_id":      COL_CENTER_ID,
    "center_name":    COL_CENTER_NAME,
    "center_tel":     COL_CENTER_TEL,
    "center_addr":    COL_CENTER_ADDR,
    "center_daddr":   COL_CENTER_DADDR,
    "center_url":     COL_CENTER_URL,
    "center_ctpv_cd": COL_CENTER_CTPV_CD,
    "center_ctpv_nm": COL_CENTER_CTPV_NM,
    "center_sgg_cd":  COL_CENTER_SGG_CD,
    "center_sgg_nm":  COL_CENTER_SGG_NM,
}

# API 응답 필드명 → DB 컬럼명 매핑
POLICY_API_FIELD_MAP = {
    "plcyNo":           COL_POLICY_ID,
    "plcyNm":           COL_POLICY_NAME,
    "plcyKywdNm":       COL_KEYWORD,
    "plcyExplnCn":      COL_DESCRIPTION,
    "lclsfNm":          COL_CATEGORY_MAIN,
    "mclsfNm":          COL_CATEGORY_SUB,
    "plcySprtCn":       COL_SUPPORT_CONTENT,
    "plcyPvsnMthdCd":   COL_PVSN_METHOD,
    "sprvsnInstCdNm":   COL_INSTITUTION,
    "sprvsnInstPicNm":  COL_INSTITUTION_MANAGER,
    "operInstCdNm":     COL_OPER_INST,
    "sprtSclCnt":       COL_SUPPORT_SCALE,
    "sprtArvlSeqYn":    COL_ARRIVE_SEQ,
    "aplyPrdSeCd":      COL_APPLY_PERIOD_TYPE,
    "bizPrdSeCd":       COL_BIZ_PERIOD_TYPE,
    "bizPrdBgngYmd":    COL_BIZ_START_DATE,
    "bizPrdEndYmd":     COL_BIZ_END_DATE,
    "bizPrdEtcCn":      COL_BIZ_PERIOD_ETC,
    "plcyAplyMthdCn":   COL_APPLY_METHOD,
    "srngMthdCn":       COL_SELECTION_METHOD,
    "aplyUrlAddr":      COL_APPLICATION_URL,
    "sbmsnDcmntCn":     COL_SUBMIT_DOCS,
    "etcMttrCn":        COL_ETC,
    "refUrlAddr1":      COL_REF_URL1,
    "refUrlAddr2":      COL_REF_URL2,
    "aplyYmd":          COL_APPLY_PERIOD,      
    "sprtTrgtMinAge":   COL_MIN_AGE,
    "sprtTrgtMaxAge":   COL_MAX_AGE,
    "sprtTrgtAgeLmtYn": COL_AGE_LIMIT,
    "mrgSttsCd":        COL_MARRIAGE_STATUS,
    "earnCndSeCd":      COL_INCOME_TYPE,
    "earnMinAmt":       COL_INCOME_MIN,
    "earnMaxAmt":       COL_INCOME_MAX,
    "earnEtcCn":        COL_INCOME_ETC,
    "addAplyQlfcCndCn": COL_APPLY_CONDITION,
    "ptcpPrpTrgtCn":    COL_EXCLUDED_TARGET,
    "zipCd":            COL_REGION,
    "plcyMajorCd":      COL_MAJOR_CD,
    "jobCd":            COL_JOB_CD,
    "schoolCd":         COL_SCHOOL_CD,
    "sbizCd":           COL_SPECIAL_CD,
    "frstRegDt":        COL_FIRST_REG_DATE,
    "lastMdfcnDt":      COL_LAST_MOD_DATE,
}

CENTER_API_FIELD_MAP = {
    "cntrSn":       COL_CENTER_ID,
    "cntrNm":       COL_CENTER_NAME,
    "cntrTelno":    COL_CENTER_TEL,
    "cntrAddr":     COL_CENTER_ADDR,
    "cntrDaddr":    COL_CENTER_DADDR,
    "cntrUrlAddr":  COL_CENTER_URL,
    "stdgCtpvCd":   COL_CENTER_CTPV_CD,
    "stdgCtpvCdNm": COL_CENTER_CTPV_NM,
    "stdgSggCd":    COL_CENTER_SGG_CD,
    "stdgSggCdNm":  COL_CENTER_SGG_NM,
}

# ── policies_processed 테이블 컬럼명 ─────────────────────────
# policies 테이블과 동일한 구조
# 전처리가 들어가는 테이블
# preprocessing.py가 코드 변환 + search_text 생성 후 여기에 저장
POLICY_PROCESSED_COLUMNS = POLICY_COLUMNS.copy()