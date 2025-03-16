from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
import os

app = Flask(__name__)
app.secret_key = 'dindin_secret_key'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'dindin.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(64), nullable=False)
    recipes = relationship('Recipe', backref='user', cascade="all, delete-orphan")
    inventory = relationship('InventoryItem', backref='user', cascade="all, delete-orphan")
    grocery_list = relationship('GroceryItem', backref='user', cascade="all, delete-orphan")

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    required_for = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

with app.app_context():
    db.create_all()

@app.route('/')
def login():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def handle_login():
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session['username'] = username
        return redirect(url_for('inventory'))
    else:
        return "Invalid username or password"

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def handle_register():
    username = request.form['username']
    password = request.form['password']
    if User.query.filter_by(username=username).first():
        return "Username already exists!"
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('login'))

@app.route('/inventory')
def inventory():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=username).first()
    inventory = InventoryItem.query.filter_by(user_id=user.id).all()
    sorted_inventory = {}
    for item in inventory:
        sorted_inventory.setdefault(item.category, []).append(item.item)
    for cat in sorted_inventory:
        sorted_inventory[cat].sort(key=lambda x: x.lower())
    return render_template('inventory.html', categories=sorted_inventory, username=username)

@app.route('/add-item', methods=['POST'])
def add_item():
    username = session.get('username')
    item = request.form['item'].strip()
    category = request.form['category']
    user = User.query.filter_by(username=username).first()

    # Check if item is already in grocery list — prevent adding it to inventory
    existing_grocery = GroceryItem.query.filter_by(user_id=user.id, item=item).first()
    if existing_grocery:
        return f"Item '{item}' is currently in your grocery list. Restock it from grocery list instead."

    # Check if item already in inventory (optional if you want to avoid duplicate inventory entries)
    existing_inventory = InventoryItem.query.filter_by(user_id=user.id, item=item, category=category).first()
    if not existing_inventory:
        db.session.add(InventoryItem(item=item, category=category, user_id=user.id))
        db.session.commit()

    return redirect(url_for('inventory'))

@app.route('/delete-item', methods=['POST'])
def delete_item():
    username = session.get('username')
    item = request.form['item']
    category = request.form['category']
    user = User.query.filter_by(username=username).first()
    InventoryItem.query.filter_by(user_id=user.id, item=item, category=category).delete()
    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/move-to-grocery', methods=['POST'])
def move_to_grocery():
    username = session.get('username')
    item = request.form['item']
    category = request.form['category']
    user = User.query.filter_by(username=username).first()

    # ✅ Remove item from inventory first
    InventoryItem.query.filter_by(user_id=user.id, item=item, category=category).delete()

    # ✅ Check if it's already in grocery list
    existing = GroceryItem.query.filter_by(user_id=user.id, item=item).first()
    if not existing:
        db.session.add(GroceryItem(item=item, category=category, user_id=user.id))

    db.session.commit()
    return redirect(url_for('inventory'))

@app.route('/grocerylist')
def grocerylist():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=username).first()
    grocery_list = GroceryItem.query.filter_by(user_id=user.id).all()
    sorted_list = sorted(grocery_list, key=lambda x: (x.category.lower(), x.item.lower()))
    return render_template('grocerylist.html', grocery_list=sorted_list, username=username)

@app.route('/move-to-inventory', methods=['POST'])
def move_to_inventory():
    username = session.get('username')
    item = request.form['item']
    user = User.query.filter_by(username=username).first()
    grocery = GroceryItem.query.filter_by(user_id=user.id, item=item).first()
    if grocery:
        db.session.delete(grocery)
        db.session.add(InventoryItem(item=item, category=grocery.category, user_id=user.id))
        db.session.commit()
    return redirect(url_for('grocerylist'))

@app.route('/recipes')
def recipes():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=username).first()
    recipes = Recipe.query.filter_by(user_id=user.id).all()
    inventory = InventoryItem.query.filter_by(user_id=user.id).all()
    all_inventory = [item.item for item in inventory]
    recipe_missing = {
        r.name: [i for i in r.ingredients.split(', ') if i not in all_inventory]
        for r in recipes
    }
    return render_template('recipes.html', recipes=recipes, recipe_missing=recipe_missing, username=username)

@app.route('/add-recipe', methods=['POST'])
def add_recipe():
    username = session.get('username')
    recipe_name = request.form['recipe_name'].strip()
    ingredients = [i.strip() for i in request.form['ingredients'].split(',') if i.strip()]
    user = User.query.filter_by(username=username).first()
    db.session.add(Recipe(name=recipe_name, ingredients=', '.join(ingredients), user_id=user.id))
    db.session.commit()
    return redirect(url_for('recipes'))

@app.route('/delete-recipe', methods=['POST'])
def delete_recipe():
    username = session.get('username')
    recipe_name = request.form['recipe_name']
    user = User.query.filter_by(username=username).first()
    Recipe.query.filter_by(user_id=user.id, name=recipe_name).delete()
    db.session.commit()
    return redirect(url_for('recipes'))

@app.route('/prepare-recipe', methods=['POST'])
def prepare_recipe():
    username = session.get('username')
    recipe_name = request.form['recipe_name']
    user = User.query.filter_by(username=username).first()
    recipe = Recipe.query.filter_by(user_id=user.id, name=recipe_name).first()
    inventory = InventoryItem.query.filter_by(user_id=user.id).all()
    all_inventory = [i.item for i in inventory]
    missing = [i for i in recipe.ingredients.split(', ') if i not in all_inventory]
    for i in missing:
        existing = GroceryItem.query.filter_by(user_id=user.id, item=i).first()
        if existing:
            if existing.required_for:
                rset = set(existing.required_for.split(', '))
                rset.add(recipe_name)
                existing.required_for = ', '.join(sorted(rset))
            else:
                existing.required_for = recipe_name
        else:
            db.session.add(GroceryItem(item=i, category="Other", required_for=recipe_name, user_id=user.id))
    db.session.commit()
    return redirect(url_for('grocerylist'))

@app.route('/unprepare-recipe', methods=['POST'])
def unprepare_recipe():
    username = session.get('username')
    recipe_name = request.form['recipe_name']
    user = User.query.filter_by(username=username).first()
    items = GroceryItem.query.filter_by(user_id=user.id).all()
    for i in items:
        if i.required_for:
            required = [r.strip() for r in i.required_for.split(', ') if r.strip()]
            if recipe_name in required:
                required.remove(recipe_name)
                i.required_for = ', '.join(required) if required else None
    db.session.commit()
    return redirect(url_for('grocerylist'))

# Create tables before app runs
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
