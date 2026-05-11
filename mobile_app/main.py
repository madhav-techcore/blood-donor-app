from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen

from login_screen import LoginScreen
from register_screen import RegisterScreen
from donor_screen import DonorScreen

KV_DIR = "kv"

class RootScreenManager(ScreenManager):
    pass

class BloodDonorApp(App):
    def build(self):
        self.title = "Blood Donor App"
        Builder.load_file("mobile_app/kv/login.kv")
        Builder.load_file("mobile_app/kv/home.kv")
        Builder.load_file("mobile_app/kv/donor.kv")

        sm = RootScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(RegisterScreen(name="register"))
        sm.add_widget(DonorScreen(name="donor"))
        return sm

if __name__ == "__main__":
    BloodDonorApp().run()
