from qatar_pii_scan.detectors import detect, is_name_field


def found(text, field=""):
    return [(m.kind, m.value, m.confidence) for m in detect(text, field)]


def test_passport_needs_a_keyword():
    assert found("passport no: AB1234567") == [("passport", "AB1234567", "medium")]
    assert found("رقم الجواز: N12345678") == [("passport", "N12345678", "medium")]
    assert found("order AB1234567") == []
    assert found("P0012345", field="passport_number") == [("passport", "P0012345", "medium")]


def test_name_fields():
    assert is_name_field("customer_name")
    assert is_name_field("fullName")
    assert is_name_field("الاسم")
    assert not is_name_field("file_name")
    assert not is_name_field("hostname")
    assert not is_name_field("product name")
    assert not is_name_field("username")


def test_values_in_name_fields_are_low_confidence():
    assert found("Noor Al-Mansoori", field="full_name") == [("name", "Noor Al-Mansoori", "low")]
    assert found("نور المنصوري", field="الاسم") == [("name", "نور المنصوري", "low")]
    assert found("Noor Al-Mansoori", field="city") == []
    assert found("n/a", field="name") == []
    assert found("Order #12", field="customer") == []


def test_names_in_free_text():
    assert found("Ticket raised by Mr. Karim Haddad today") == [("name", "Karim Haddad", "low")]
    assert found('customer_name = "Sara Yousef"') == [("name", "Sara Yousef", "low")]
    assert found("وصل طلب السيدة مريم الكعبي اليوم")[0][1].startswith("مريم الكعبي")
    assert found("الموظف خالد بن سالم المري")[0] == ("name", "خالد بن سالم المري", "low")


def test_name_assignment_needs_two_words():
    assert found("name = Admin") == []
    assert found("class Name:") == []


def test_placeholder_names_are_skipped():
    assert found("Guest", field="name") == []
    assert found("زائر", field="الاسم") == []
