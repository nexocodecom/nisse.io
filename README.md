# nisse.io

Meet Nisse, your Slack team little helper!

Nisse is an open source app and Slackbot for reporting and managing your team's workload.
#### Easy tracking
Nisse Slackbot will let you track your daily workload in a seamless way! Just talk to him!
####  Daily reminders
Nisse will remind you to log your work every day, so no need to worry about it!
#### Admin reports
Admin gets access to reports with time logs and work submitted by each team member.

Feel free to contribute, comment, report an issue or, what’s the most important, use it yourself. **_Let Nisse help you!_**

## Running app
- install all required packages by running:
    ```
    pip install -r requirements.txt
    ```

- set application environment to desired one, environment name should match one of the files in `/config` directory.
   >This step requires repeating when PC was rebooted or command prompt restarted.

    Unix Bash (Linux, Mac, etc.):
    ```
    $ export APP_CONFIG_FILE=local
    $ export FLASK_ENV=local
    $ export FLASK_APP=local
    ```

    Windows CMD:
    ```
    set APP_CONFIG_FILE=local
    set FLASK_ENV=local
    set FLASK_APP=local
    ```

    Windows PowerShell:
    ```
    $env:APP_CONFIG_FILE="local"
    $env:FLASK_ENV = "local"
    $env:FLASK_APP = "nisse"
    ```

- create configuration file in `/config` directory matching your APP_CONFIG_FILE environment variable.
    Eg. if you executed command
    ```
    $env:APP_CONFIG_FILE = "development" 
    ```

    you should have a file named `development.py` in your `/config` directory. Within this file you should define connection string, database port and SQLAlchemy orm tracking setting using following manner:
    ```
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/nisse_db'
    SQLALCHEMY_DATABASE_PORT = 3306
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ```
- create empty database named `nisse_db` - this is required, otherwise application won't start
- migrate database to latest version.

     to check if database is up to date run
     ```
     flask db current
     ```
     This command should output something like: migration_hash (head) if database is up to date. 
     ```
     dbc11c363b7f (head)
     ```
    
    To migrate database to latest version, execute:
    ```
    flask db upgrade
    ```
- to run application just execute following command:

    Unix Bash (Linux, Mac, etc.):
    ```
    $ flask run    
    ```

    Windows CMD or PowerShell:
    ```
    flask run    
    ```

    if required, multiple parameters are available to pass when running application:
    ```
    flask run -h localhost -p 5002 
    ```
    above command will run app instance on localhost on port 5002.


### Migrations
Performing migrations is limited to a few CLI command.
Make changes to the database model, and then just run command to create migration file: 
```
flask db migrate -m your_migration_name
```
After migrating database, generated migration file MUST BE reviewed as the auto-gen tool has limitations when detecting changes.

Here is full list of migration limitations: 
http://alembic.zzzcomputing.com/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect

Besides of review, ALWAYS test downgrade operation on your local machine, this will prevent potential problems when downgrading migrations.

Remember, -m parameter is not required, but it is good to give a migration some title which make it easier to know what particular migration actually does.

#### Potential pitfalls detected during migrations development
> This list should be constantly expaned while gaining more and more experience with flask migrations.

- when new foreign key constraint is created, ALWAYS add it appropriate name instead of python `None` - this will allow seamless downgrade operation
    migration operation generated like this:
    ```
    op.create_foreign_key(None, 'time_entries', 'users', ['user_id'], ['user_id'])
    ```
    should be changed to this:
    ```
    op.create_foreign_key('fk_timeentries_user', 'time_entries', 'users', ['user_id'], ['user_id'])
    ```


To actually perfrom migration on database, execute: 
```
flask db upgrade
```

### Package management
When new package is installed and it is required by application, it should be added to `requirements.txt` file, so other developers could simply 
install new packages by running command: 
```
pip install -r requirements.txt
```
