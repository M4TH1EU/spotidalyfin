import subprocess

from syncphony.utils.logger import log


def convert_m4a_bytes_to_flac(input_bytes: bytes, timeout=10, re_encode_flac: bool = False) -> bytes:
    """
    Convert an M4A byte stream with a FLAC audio stream to a FLAC byte stream.

    Args:
        input_bytes (bytes): Input M4A data as a byte array.
        timeout (int): Timeout for the conversion process.
        reencode_flac (bool): Whether to re-encode the FLAC audio stream instead of copying it (ffmpeg option)

    Returns:
        bytes: Output FLAC data as a byte array.
    """
    try:
        # Run FFmpeg with stdin (input) and stdout (output)
        process = subprocess.run(
            [
                "ffmpeg",
                "-i", "pipe:0",  # Use pipe as input (stdin)
                "-f", "flac",  # Specify output format as FLAC
                # Copy audio codec (no re-encoding it's already FLAC inside M4A)
                "-c:a", "copy" if not re_encode_flac else "flac",
                "pipe:1"  # Use pipe as output (stdout)
            ],
            input=input_bytes,  # Provide the byte array as input
            stdout=subprocess.PIPE,  # Capture stdout for the FLAC output
            stderr=subprocess.PIPE,  # Capture errors for debugging
            timeout=timeout
        )

        # Check if FFmpeg succeeded
        if process.returncode != 0:
            raise subprocess.SubprocessError(f"FFmpeg error: {process.stderr.decode()}")

        return process.stdout  # Return FLAC audio as bytes
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg process timed out")
    except subprocess.SubprocessError as e:
        if not re_encode_flac:
            log.debug("Failed to convert M4A to FLAC. Trying to re-encode in FLAC instead of copy...")
            return convert_m4a_bytes_to_flac(input_bytes, timeout, re_encode_flac=True)
        else:
            raise RuntimeError(f"Error during FFmpeg conversion: {e}")