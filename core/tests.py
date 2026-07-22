from django.test import SimpleTestCase
from django.urls import reverse


class AdSenseVerificationTests(SimpleTestCase):
    publisher_id = "2037181352494119"

    def test_ads_txt_is_available_at_site_root(self):
        response = self.client.get(reverse("core:ads_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertEqual(
            response.content.decode(),
            f"google.com, pub-{self.publisher_id}, DIRECT, f08c47fec0942fa0\n",
        )
