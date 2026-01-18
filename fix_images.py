from app import app, db, Menu
import os

with app.app_context():
    items = Menu.query.all()

    for item in items:
        if item.image:
            # Extract only the filename
            filename = os.path.basename(item.image)
            # Update DB path to be relative to static/images/
            item.image = f"images/{filename}"

    db.session.commit()

print("Image paths fixed successfully")
