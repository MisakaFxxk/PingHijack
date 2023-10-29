import flask
from flask import  make_response, redirect, request

api = flask.Flask(__name__) 


# @api.before_request
# def before_request():
#     if not request.is_secure:
#         url = request.url.replace('http://', 'https://', 1)
#         return redirect(url, code=301)

@api.route('/generate_204', methods=["GET", "POST","HEAD"])
def update():
    response = make_response('')
    response.status_code = 204
    return response



if __name__ == '__main__':
    api.run(port=80,debug=True,host='127.0.0.1')