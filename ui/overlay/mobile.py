from ui.lib.model_view import ModelView

class MobileOverlay(ModelView):
    DOM_ELEMENT_CLASS = "mobile-overlay"
    TEMPLATE_STR = '''
        <div class="mobile-overlay" id="mobileOverlay" onclick="closeMobileSidebar()"></div>

    '''