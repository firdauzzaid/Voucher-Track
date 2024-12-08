from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import pymysql
import pymysql.cursors
import base64

app = Flask(__name__)
app.secret_key = "your_secret_key"

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "horus_Firdaus_db",
    "cursorclass": pymysql.cursors.DictCursor
}


def get_connection():
    return pymysql.connect(**db_config)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                sql = "SELECT * FROM user WHERE username = %s AND password = %s"
                cursor.execute(sql, (username, password))
                user = cursor.fetchone()

            if user:
                session['user_id'] = user['id']
                flash("Login berhasil!", "success")
                return redirect(url_for('voucher'))
            else:
                flash("Username atau password salah!", "error")
                return redirect(url_for('login'))

        except pymysql.MySQLError as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('login'))

        finally:
            conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        nama = request.form['nama']
        tanggal_daftar = request.form['tanggal_daftar']

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO user (username, password, email, nama, tanggal_daftar)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (username, password, email, nama, tanggal_daftar))
                conn.commit()

            flash("Registrasi berhasil!", "success")
            return redirect(url_for('login'))

        except pymysql.MySQLError as e:
            flash(f"Error: {str(e)}", "error")
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/voucher')
def voucher():
    selected_category = request.args.get('category', 'all')

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT kategori FROM voucher")
            categories = [row['kategori'] for row in cursor.fetchall()]

            if selected_category == 'all':
                cursor.execute("SELECT * FROM voucher WHERE status='Available'")
            else:
                cursor.execute(
                    "SELECT * FROM voucher WHERE kategori=%s AND status='Available'",
                    (selected_category,)
                )

            vouchers = cursor.fetchall()

            for voucher in vouchers:
                if voucher['foto']:
                    voucher['foto'] = f"data:image/jpeg;base64,{base64.b64encode(voucher['foto']).decode('utf-8')}"

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        vouchers = []
        categories = []

    return render_template('voucher.html', vouchers=vouchers, categories=categories,
                           selected_category=selected_category)


@app.route('/claim_voucher/<int:id_voucher>', methods=['POST'])
def claim_voucher(id_voucher):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT status FROM voucher WHERE id=%s", (id_voucher,))
            voucher = cursor.fetchone()
            if not voucher or voucher['status'] != 'Available':
                return jsonify({"success": False, "error": "Voucher tidak tersedia untuk diklaim."})

            user_id = session.get('user_id')  # Pastikan user_id tersimpan di sesi
            if not user_id:
                return jsonify({"success": False, "error": "Anda harus login untuk mengklaim voucher."})

            cursor.execute("""
                INSERT INTO voucher_claim (id_voucher, id_user, tanggal_claim)
                VALUES (%s, %s, NOW())
            """, (id_voucher, user_id))
            cursor.execute("UPDATE voucher SET status='Claimed' WHERE id=%s", (id_voucher,))
            conn.commit()

            return jsonify({"success": True})

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return jsonify({"success": False, "error": str(e)})
    finally:
        conn.close()


@app.route('/history')
def history():
    if 'user_id' not in session:
        flash("Anda harus login untuk melihat riwayat!", "error")
        return redirect(url_for('login'))

    user_id = session['user_id']
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT vc.id, v.nama, v.kategori, vc.tanggal_claim 
                FROM voucher_claim vc
                JOIN voucher v ON vc.id_voucher = v.id
                WHERE vc.id_user = %s
            """, (user_id,))
            claimed_vouchers = cursor.fetchall()

            claim_count = {}
            for claim in claimed_vouchers:
                category = claim['kategori']
                if category not in claim_count:
                    claim_count[category] = 0
                claim_count[category] += 1

            total_claimed = len(claimed_vouchers)

        return render_template('history.html',
                               claimed_vouchers=claimed_vouchers,
                               claim_count=claim_count,
                               total_claimed=total_claimed)
    except pymysql.MySQLError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('history'))
    finally:
        conn.close()


@app.route('/delete_claim/<int:claim_id>', methods=['POST'])
def delete_claim(claim_id):
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM voucher_claim WHERE id = %s", (claim_id,))
            claim = cursor.fetchone()

            if claim:
                cursor.execute("DELETE FROM voucher_claim WHERE id = %s", (claim_id,))

                cursor.execute("""
                    UPDATE voucher SET status = 'Available' 
                    WHERE id = %s
                """, (claim['id_voucher'],))

                conn.commit()
                flash("Voucher berhasil dikembalikan ke daftar!", "success")
            else:
                flash("Voucher tidak ditemukan!", "error")

        return redirect(url_for('history'))

    except pymysql.MySQLError as e:
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('history'))

    finally:
        conn.close()
        

if __name__ == '__main__':
    app.run(debug=True)
