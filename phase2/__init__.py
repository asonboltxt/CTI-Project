from .routes import phase2_bp


def register_phase2(app):
    app.register_blueprint(phase2_bp)
