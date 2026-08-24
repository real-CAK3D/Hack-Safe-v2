import unittest

from spac3ghost.personality import event_from_status


class ServiceCacheFlagTests(unittest.TestCase):
    def test_event_from_status_ignores_cached_service_flag(self):
        status = {'services': {'ssh': {'active': True}, 'gpsd': {'active': False}, 'cached': True}, 'wifi': {}, 'sensors': {}}
        event = event_from_status(status)
        self.assertEqual(event['kind'], 'service')
        self.assertIn('gpsd', event['text'])


if __name__ == '__main__':
    unittest.main()
