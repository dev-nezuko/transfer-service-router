# Mozio Test Project

## Setup

The first thing to do is to clone the repository:

```sh
$ git clone https://github.com/dev-nezuko/transfer-service-router.git
$ cd transfer-service-router
```

Create a virtual environment to install dependencies in and activate it:

```sh
$ virtualenv mozio-env
$ source env/bin/activate
```

Then install the dependencies:
- Make sure you have Postgres and PostGIS installed
```sh
(mozio-env)$ pip install -r requirements.txt
```

Once `pip` has finished downloading the dependencies:
- Make sure to add `username` and `password` for database in `settings.py`
```sh
(mozio-env)$ cd mozio-test
(mozio-env)$ python manage.py migrate
(mozio-env)$ python manage.py runserver
```

## Walkthrough
- Navigate to `http://127.0.0.1:8000/testapp/provider` on your browser and from there you can perform CRUD for a Provider
- Navigate to `http://127.0.0.1:8000/testapp/service_area` on your browser and from there you can perform CRUD for a Service Area
- Navigate to `http://127.0.0.1:8000/testapp/search_service_area?lat=<latitude>&lng=<longtitude>` by replacing `<latitude>` and `<longitude>` with the coordinates you want to search with
