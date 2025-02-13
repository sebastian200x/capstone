from flask import Flask, render_template, request, redirect, url_for, Response
import mysql.connector
import cv2
from PIL import Image
import numpy as np
import os

app = Flask(__name__)

mydb = mysql.connector.connect(
    host="localhost", user="root", passwd="", database="flask_db"
)
mycursor = mydb.cursor()

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Generate dataset >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def generate_dataset(nbr):
    face_classifier = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def face_cropped(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray, 1.3, 5)
        # scaling factor=1.3
        # Minimum neighbor = 5

        if faces is ():
            return None
        for x, y, w, h in faces:
            cropped_face = img[y : y + h, x : x + w]
        return cropped_face

    cap = cv2.VideoCapture(0)

    mycursor.execute("select ifnull(max(img_id), 0) from img_dataset")
    row = mycursor.fetchone()
    lastid = row[0]

    img_id = lastid
    max_imgid = img_id + 100
    count_img = 0

    while True:
        ret, img = cap.read()
        if face_cropped(img) is not None:
            count_img += 1
            img_id += 1
            face = cv2.resize(face_cropped(img), (200, 200))
            face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)

            file_name_path = "dataset/" + nbr + "." + str(img_id) + ".jpg"
            cv2.imwrite(file_name_path, face)
            cv2.putText(
                face,
                str(count_img),
                (50, 50),
                cv2.FONT_HERSHEY_COMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            mycursor.execute(
                """INSERT INTO `img_dataset` (`img_id`, `img_person`) VALUES
                                ('{}', '{}')""".format(
                    img_id, nbr
                )
            )
            mydb.commit()

            frame = cv2.imencode(".jpg", face)[1].tobytes()
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

            if cv2.waitKey(1) == 13 or int(img_id) == int(max_imgid):
                break
                cap.release()
                cv2.destroyAllWindows()


# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Train Classifier >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
@app.route("/train_classifier/<nbr>")
def train_classifier(nbr):
    dataset_dir = "dataset/"

    path = [os.path.join(dataset_dir, f) for f in os.listdir(dataset_dir)]
    faces = []
    ids = []

    for image in path:
        img = Image.open(image).convert("L")
        imageNp = np.array(img, "uint8")
        id = int(os.path.split(image)[1].split(".")[1])

        faces.append(imageNp)
        ids.append(id)
    ids = np.array(ids)

    # Train the classifier and save
    clf = cv2.face.LBPHFaceRecognizer_create()
    clf.train(faces, ids)

    # for pycharm
    clf.write("classifier.xml")

    # for vscode:
    # clf.write(".1 face_rec\classifier.xml")

    return redirect("/")


# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Face Recognition >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def face_recognition():  # generate frame by frame from camera
    def draw_boundary(img, classifier, scaleFactor, minNeighbors, color, text, clf):
        gray_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        features = classifier.detectMultiScale(gray_image, scaleFactor, minNeighbors)

        coords = []

        for x, y, w, h in features:
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            id, pred = clf.predict(gray_image[y : y + h, x : x + w])
            confidence = int(100 * (1 - pred / 300))

            mycursor.execute(
                "select b.prs_name "
                "  from img_dataset a "
                "  left join prs_mstr b on a.img_person = b.prs_nbr "
                " where img_id = " + str(id)
                # SELECT b.prs_name FROM img_dataset a LEFT JOIN prs_mstr b ON a.img_person = b.prs_nbr WHERE img_id = 100;
            )
            s = mycursor.fetchone()
            s = "" + "".join(s)

            if confidence > 70:
                cv2.putText(
                    img,
                    s,
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color,
                    1,
                    cv2.LINE_AA,
                )
            else:
                cv2.putText(
                    img,
                    "UNKNOWN",
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )

            coords = [x, y, w, h]
        return coords

    def recognize(img, clf, faceCascade):
        coords = draw_boundary(img, faceCascade, 1.1, 10, (255, 255, 0), "Face", clf)
        return img

    faceCascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    clf = cv2.face.LBPHFaceRecognizer_create()

    # for pycharm
    # clf.read("classifier.xml")


    # for vscode:
    clf.read(".1 face_rec\classifier.xml")

    wCam, hCam = 500, 400

    cap = cv2.VideoCapture(0)
    cap.set(3, wCam)
    cap.set(4, hCam)

    while True:
        ret, img = cap.read()
        img = recognize(img, clf, faceCascade)

        frame = cv2.imencode(".jpg", img)[1].tobytes()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

        key = cv2.waitKey(1)
        if key == 27:
            break

@app.route("/")
def home():
    mycursor.execute(
        "select prs_nbr, prs_name, prs_skill, prs_active, prs_added from prs_mstr"
    )
    data = mycursor.fetchall()

    return render_template("index.html", data=data)

# adding account page
@app.route("/addprsn")
def addprsn():
    mycursor.execute("select ifnull(max(prs_nbr) + 1, 101) from prs_mstr")
    row = mycursor.fetchone()
    nbr = row[0]
    # print(int(nbr))

    return render_template("addprsn.html", newnbr=int(nbr))

# adding account in database
@app.route("/addprsn_submit", methods=["POST"])
def addprsn_submit():
    prsnbr = request.form.get("txtnbr")
    prsname = request.form.get("txtname")
    prsskill = request.form.get("optskill")

    mycursor.execute(
        """INSERT INTO `prs_mstr` (`prs_nbr`, `prs_name`, `prs_skill`) VALUES
                    ('{}', '{}', '{}')""".format(
            prsnbr, prsname, prsskill
        )
    )
    mydb.commit()

    # return redirect(url_for('home'))
    return redirect(url_for("vfdataset_page", prs=prsnbr))

# training page
@app.route("/vfdataset_page/<prs>")
def vfdataset_page(prs):
    return render_template("gendataset.html", prs=prs)

# video for training or registering face
@app.route("/vidfeed_dataset/<nbr>")
def vidfeed_dataset(nbr):
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(
        generate_dataset(nbr), mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# video for face recognizing
@app.route("/video_feed")
def video_feed():
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(
        face_recognition(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )

# face recognizing page
@app.route("/fr_page")
def fr_page():
    return render_template("members_reg_face_cam.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=6699, debug=True)
