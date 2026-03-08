# Group F Project
"We may be group F but we are going for the A+"

todo:
- user could add notes to go with their session in a sticky header or footer or something and link to dashboard
  - (team) visual mockup
  - (team) optional html mockup
- We can add some live data to the bottom of the pages themselves ( meh.com style )
  - (team) visual mockup and/or data sets to use
  - (team) optional html mockup


# Important Notes

Note, the admin user is 
```bash
user: admin
pass: groupf
```

You can add users from /admin dashboard or via console:

```bash
python manage.py createsuperuser
```

## admin
Going to http://127.0.0.1:8000/admin/ lets you browse data in a raw format and create pages
![alt text](media/admin1.png)

You can create pages with raw html like this:
![alt text](media/admin2.png) 


## What's working right now?
1. When you add a page in the admin you can then visit it from the home page
2. You can view pages in the dashboard and look at session stats (just cliks right now)
3. There is a view that collects tracked events and you can see them in the debug log while you run your webserver, they look like this:

```bash
[19/Feb/2026 18:43:42] "GET /pages/test_page/ HTTP/1.1" 200 5800
[19/Feb/2026 18:44:56] "POST /track/event/ HTTP/1.1" 200 12
[19/Feb/2026 18:44:56] "POST /track/event/ HTTP/1.1" 200 12
[19/Feb/2026 18:44:56] "POST /track/event/ HTTP/1.1" 200 12
[19/Feb/2026 18:44:57] "POST /track/event/ HTTP/1.1" 200 12
```

4. the "track_event" function and tracking models are pretty open ended where we can sends any kind of data we want, explore the base/models.py for some ideas

---

# Web App Framework

## Getting started (Poetry)

1) Install Django (make sure you have latest python installed)

```bash
pip install django
```




5) Start the development server

```bash
python manage.py runserver
```

Open in browser:
http://127.0.0.1:8000/

---

To run database migrations ( I am checking in the db.sqlite so you don't have to do this unless you blow away the database and want a new one )

```bash
python manage.py makemigrations
python manage.py migrate
```

---

Database is simple right now, will grow as we discover more types of data to store:

```python
base/models.py

class Project(models.Model):  # The Table Name
    name = models.CharField(max_length=128)
```

---




# Bonus Database Stuff

If you want to get a visual way to browse the database, but only edit the DB using the python models

> https://sqlitebrowser.org/

![alt text](media/db.png)
