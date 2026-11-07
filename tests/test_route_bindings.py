from acceptance.universal import routes as candidate



def test_literal_prefix_and_reexport_registration_override(tmp_path):
    (tmp_path/'pkg').mkdir()
    (tmp_path/'pkg/__init__.py').write_text('from flask import Flask\nfrom . import views\napp=Flask(__name__)\napp.register_blueprint(views.bp,url_prefix="/v2")')
    (tmp_path/'pkg/views.py').write_text('from flask import Blueprint\nbp=Blueprint("example",__name__,url_prefix="/default")\n@bp.post("/submit")\ndef submit():pass')
    unit=dict(runtime='python',path='.')
    candidate.discover(tmp_path,['pkg/__init__.py','pkg/views.py'],[unit],lambda n,lang:unit)
    assert len(unit['route_bindings'])==1
    row=unit['route_bindings'][0]
    assert row['path']=='/v2/submit' and row['endpoint']=='example.submit' and row['binding']=='literal-registration'
    assert row['methods']==['POST'] and row['source']['line']==3


def test_unknown_prefix_and_multiple_registrations_are_preserved(tmp_path):
    (tmp_path/'app.py').write_text('from flask import Blueprint,Flask\nbp=Blueprint("example",__name__)\n@bp.route("/x")\ndef handler():pass\napp=Flask(__name__)\napp.register_blueprint(bp,url_prefix=environment_prefix)\napp.register_blueprint(bp,url_prefix="/known")')
    unit=dict(runtime='python',path='.')
    candidate.discover(tmp_path,['app.py'],[unit],lambda n,lang:unit)
    assert [r['path'] for r in unit['route_bindings']]==[None,'/known/x']
    assert unit['route_bindings'][0]['binding']=='registration-needs-binding'


def test_route_catalogue_never_imports_target(tmp_path):
    (tmp_path/'app.py').write_text('raise RuntimeError("never import")\nfrom flask import Flask\napp=Flask(__name__)\n@app.get("/health")\ndef status():return "not an oracle"')
    u=dict(runtime='python',path='.')
    candidate.discover(tmp_path,['app.py'],[u],lambda n,lang:u)
    row=u['route_bindings'][0]
    assert row['path']=='/health' and 'not an oracle' not in str(row)

