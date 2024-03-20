import subprocess


def get_codec(url):
    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout.decode().strip()


# Example usage:
# url = "https://govbw.vid109d224.site/_v2-wwdo/12a3c523fb105800ed8c394685aeeb0b932efd5c02bdb6b04b187baea93ece832257df1a4b6125fcfa38c35da05dee86aad28d46d73fc4e9d4e5a13b5572f1d6749544f85d4eea0d12c5f7ec7c422b4a6366d373445766c1d99ab8008de77ec76657fe1d5336eb05beec3107f41c059a/h/list;15a38634f803584ba8926411d7bee906856cab0654b5b8.m3u8"
url = "https://pnagb.vid109d224.site/_v2-oanz/12a3c523fb105800ed8c394685aeeb0b962efe5c5eb0ffba49417baea93ece832257df1a4b6125fcfa38c35da05dee86aad28d46d73fc4e9d4e5a4385375f3d7318246f6054feb4d4194afeb3c167a136362d13410043fc89ec5f7138cf97e997f40a34f5b67fc14b6aa61/h/list;15a38634f803584ba8926411d7bee906856cab0654b5b8.m3u8"
print(get_codec(url))
