# Pastele / ShowjsBot — Google Drive + Poin + Star

## Storage
- Semua media dari Up File otomatis di Google Drive.
- Bisa memakai 1 sampai 10 Google Drive.
- `GOOGLE_DRIVE_1_JSON` + `GOOGLE_DRIVE_1_FOLDER_ID` saja sudah cukup.
- Nanti Drive 2–10 dapat ditambahkan tanpa mengubah source.
- Supabase/PostgreSQL menyimpan CODE, user, transaksi, saldo, Creator, dan metadata.
- Railway hanya menjalankan bot.

## CODE
Format:
`Showjsbot_6Y91YzXy810_0p25v0d`

- `0p` = foto
- `25v` = video
- `0d` = dokumen
- random memakai angka 1–9 dan X/Y besar-kecil.

Setelah CODE dibuat, bot otomatis mem-posting ke `CODE_GROUP_ID`:
- MEDIA SAVE
- Judul
- Code
- Bot
- tombol Get File

## Unlock
Harga mengikuti jumlah media:
- Poin = 1 Poin/media untuk user biasa.
- Creator membayar 50% Poin.
- Star = 0.02 Star/media.
- Poin unlock berlaku 24 jam.
- Star unlock berlaku 48 jam.
- Setiap unlock sukses memberi Creator +1 Poin.
- Creator income = 20% dari nilai CODE (`50 media = Rp5.000`, Creator = Rp1.000).

## Check In
Hari 1–6: 0.1 Poin/hari.
Hari 7: 1 Poin.
Setelah hari 7, streak kembali ke hari 1.

## Menu
Main:
- Up File
- Get File
- Buy Poin
- Buy Star
- Buy VIP
- Menu Lainnya

Menu Lainnya:
- My Code
- Group Code
- Check In
- Help
- Creator dan Withdraw hanya untuk Creator.

## Pembayaran
Buy Poin, Buy Star, dan VIP mendukung BayarGG dan Cashi.
Admin dapat ON/OFF provider dari `/panel`.
Webhook + payment worker melakukan verifikasi otomatis.
Transaksi PAID mengirim notifikasi ke `NOTIF_CHANNEL_ID`.

## Wajib Join
Private chat dapat mewajibkan:
- Channel Saluran
- Notic Saluran

Jika user keluar dari salah satu, bot menampilkan hanya channel yang belum diikuti + tombol verifikasi.
Subscription watcher mengecek user aktif secara berkala dan mengirim pengingat.

## Smart replies
- Kirim CODE → tombol Get File.
- Kirim media → tombol Up File.
- Kirim `group`, `vip`, atau `video` → tombol Group Chat Code + Channel Notifikasi.
- Kirim `poin` → saldo Poin + Buy Poin.
- Kirim `star` → saldo Star + Buy Star.

## Setup
1. Jalankan `database.sql` di Supabase.
2. Isi `.env` berdasarkan `.env.example`.
3. Share folder Google Drive ke service account.
4. Deploy ke Railway.
5. Pastikan bot memiliki akses yang diperlukan ke channel subscription dan group CODE.
