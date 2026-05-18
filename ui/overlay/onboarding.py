from ui.lib.model_view import ModelView

class OnboardingOverlay(ModelView):
    DOM_ELEMENT_CLASS = "onboarding-overlay"
    DOM_ELEMENT_EXTRAS = 'style="display:none" role="dialog" aria-modal="true" aria-labelledby="onboardingTitle"'
    TEMPLATE_STR = '''
        <div class="onboarding-card">
            <div class="onboarding-shell">
                <div class="onboarding-sidebar">
                    <div class="onboarding-badge" data-i18n="onboarding_badge">FIRST RUN</div>
                    <h2 id="onboardingTitle" data-i18n="onboarding_title">Welcome to Hermes Web UI</h2>
                    <p id="onboardingLead" data-i18n="onboarding_lead">A quick guided setup will check your Hermes install, choose a workspace and model, and optionally protect the app with a password.</p>
                    <div class="onboarding-steps" id="onboardingSteps"></div>
                </div>
                <div class="onboarding-main">
                    <div class="onboarding-status" id="onboardingNotice"></div>
                    <div class="onboarding-body" id="onboardingBody"></div>
                    <div class="onboarding-actions">
                        <button class="sm-btn" id="onboardingBackBtn" onclick="prevOnboardingStep()" style="display:none" data-i18n="onboarding_back">Back</button>
                        <button class="sm-btn" id="onboardingSkipBtn" onclick="skipOnboarding()" style="margin-right:auto;opacity:.7" data-i18n="onboarding_skip">Skip setup</button>
                        <button class="sm-btn" id="onboardingNextBtn" onclick="nextOnboardingStep()" style="font-weight:700;color:var(--blue);border-color:rgba(124,185,255,.32)" data-i18n="onboarding_continue">Continue</button>
                    </div>
                </div>
            </div>
        </div>
    '''