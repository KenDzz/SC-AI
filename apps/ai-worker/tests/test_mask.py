from app.mask import mask_stream_url


def test_mask_rtsp_password():
    masked = mask_stream_url("rtsp://operator:s3cret@10.0.0.8/stream")
    assert masked == "rtsp://operator:***@10.0.0.8/stream"
    assert "s3cret" not in masked


def test_file_key_is_unchanged():
    assert mask_stream_url("videos/cam-1.mp4") == "videos/cam-1.mp4"
    assert mask_stream_url(None) is None
