from flask import Flask, jsonify, request
from database import init_db, get_db_connection

app = Flask(__name__)

init_db()

@app.route("/status")
def status():
    return jsonify({"status": "ok", "service": "blood donor backend"})

@app.route("/donors", methods=["GET"])
def list_donors():
    conn = get_db_connection()
    donors = conn.execute("SELECT id, name, blood_type, city FROM donors").fetchall()
    conn.close()
    return jsonify([dict(donor) for donor in donors])

@app.route("/donors", methods=["POST"])
def add_donor():
    data = request.get_json() or {}
    name = data.get("name")
    blood_type = data.get("blood_type")
    city = data.get("city")
    if not all([name, blood_type, city]):
        return jsonify({"error": "name, blood_type, and city are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO donors (name, blood_type, city) VALUES (?, ?, ?)",
        (name, blood_type, city),
    )
    conn.commit()
    donor_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": donor_id, "name": name, "blood_type": blood_type, "city": city}), 201

if __name__ == "__main__":
    app.run(debug=True, port=5000)
