from .module_router import route_task, AmbiguousTaskError

def test_flower_bush_3d_goes_to_object_only():
    assert route_task("tạo bụi hoa 3D cho game").module == "do_vat_3d"

def test_character_3d_goes_to_character_only():
    assert route_task("tạo nhân vật nữ cung thủ 3D").module == "nhan_vat_3d"

def test_character_with_weapon_still_character():
    assert route_task("tạo nhân vật cung thủ 3D cầm cung").module == "nhan_vat_3d"

def test_image_request_never_routes_3d():
    assert route_task("tạo ảnh AI nữ cung thủ", requested_output="image").module == "tao_anh_ai"

def test_video_request_never_routes_image_or_3d():
    assert route_task("tạo video AI 15 giây", requested_output="video").module == "tao_video_ai"

def test_ambiguous_3d_fails_closed():
    try:
        route_task("tạo một thứ 3D lạ")
    except AmbiguousTaskError:
        return
    raise AssertionError("must fail closed")
