from flask import Flask, request
app = Flask(__name__)

@app.route(u'/groupme/famablama', methods=[u'POST'])
def hello_word():
    j = request.get_json()
    if u'name' in j and u'text' in j:
        print(u'{name} said: {text}'.format(**j))
    return u'Thank you.'

if __name__ == u'__main__':
    app.run(debug=True, host=u'0.0.0.0')
