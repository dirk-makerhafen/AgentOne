from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class RevertFileModalView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="revertFileModal" class="modal" style="display:none;">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close-button" onclick="pyview.cancel_revert()">&times;</span>
                <h2>Confirm Revert File</h2>
            </div>
            <div class="modal-body">
                <p>Are you sure you want to revert the file <strong><span id="revertFilePath"></span></strong> to its state at <span id="revertFileTimestamp"></span>?</p>
                <p>This action cannot be undone for this specific file.</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="pyview.cancel_revert()">Cancel</button>
                <button class="btn btn-danger" id="confirmRevertFileBtn" onclick="pyview.confirm_revert()">Revert File</button>
            </div>
        </div>
    </div>
    """
    def confirm_revert(self): pass
    def cancel_revert(self): pass

class RevertAllFsModalView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="revertAllFsModal" class="modal" style="display:none;">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close-button" onclick="pyview.cancel_revert_all()">&times;</span>
                <h2>Confirm Revert ALL Filesystem Changes</h2>
            </div>
            <div class="modal-body">
                <p>You are about to revert ALL filesystem changes for this agent instance to the state at <strong><span id="revertAllFsTimestamp"></span></strong>.</p>
                <p>This will undo all file modifications, creations, and deletions made after that point.</p>
                <p class="text-danger"><strong>This action is irreversible!</strong></p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="pyview.cancel_revert_all()">Cancel</button>
                <button class="btn btn-danger" id="confirmRevertAllFsBtn" onclick="pyview.confirm_revert_all()">Revert All Changes</button>
            </div>
        </div>
    </div>
    """
    def confirm_revert_all(self): pass
    def cancel_revert_all(self): pass
