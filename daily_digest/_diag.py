import os, time

base = r"E:\个人项目\每日信息整合推送\daily_digest"
out = []

qr = os.path.join(base, "weread_login_qr.png")
if os.path.exists(qr):
    out.append(f"QR exists=True size={os.path.getsize(qr)} age_s={round(time.time()-os.path.getmtime(qr))}")
else:
    out.append("QR exists=False")

logp = os.path.join(base, "login_log.txt")
if os.path.exists(logp):
    b = open(logp, "rb").read()
    out.append(f"LOG bytes={len(b)}")
    decoded = False
    for enc in ("utf-16", "utf-8", "gbk", "latin-1"):
        try:
            t = b.decode(enc)
            out.append(f"--- decoded as {enc} (last 2500 chars) ---")
            out.append(t[-2500:])
            decoded = True
            break
        except Exception as e:
            out.append(f"decode {enc} failed: {e}")
    if not decoded:
        out.append("could not decode log")
else:
    out.append("NO LOG FILE")

open(os.path.join(base, "_diag.txt"), "w", encoding="utf-8").write("\n".join(out))
print("DIAG_WRITTEN")
