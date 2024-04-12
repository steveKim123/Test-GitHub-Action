import pytz
import os
from datetime import datetime
from dateutil.parser import parse as dt_parse

# set the default time zone to use
tz = pytz.timezone('America/Toronto')
utc = pytz.utc


# the main base class
class CatalogHelpers():
    def catalog(self):
        '''
        Integration Catalog entry point
        '''
        pass

    # get parsed default date
    def get_default_date(self):
        default_date = self.get_parsed_date('1970-01-01T00:00:00+00:00', tz=utc)
        return default_date

    # get the current date time
    def get_date_now(self):
        date_now = datetime.now(utc).replace(microsecond=0).astimezone(tz)
        return date_now

    # check if the item is available
    def is_available(self, expiration_date):
        date_now = self.get_date_now()
        default_date = self.get_default_date()
        exp_date = self.get_parsed_date(expiration_date, tz=tz)
        if date_now <= exp_date or exp_date == default_date:
            return True
        else:
            return False

    # get the channel link
    def get_channel_link(self):
        content_services_domain = '{}/templates/catalog'.format(
            os.environ.get(
                'CONTENT_SERVICES_DOMAIN',
                'http://localhost:8000'
            )
        )
        return content_services_domain

    # get the item parsed date
    def get_parsed_date(self, date_str, tz=utc,
                        default='1970-01-01T00:00:00+00:00'):
        if isinstance(date_str, datetime):
            parsed_date = date_str
        else:
            try:
                parsed_date = dt_parse(date_str)
            except Exception:
                parsed_date = dt_parse(default)

        if tz is not None:
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=utc)
            parsed_date = parsed_date.astimezone(tz)

        return parsed_date

    # get the item available/valid date
    def get_valid_date(self, available_date, expiration_date):
        available_date = self.get_parsed_date(available_date, tz=tz)
        available_date_str = available_date.isoformat()
        exp_date = self.get_parsed_date(expiration_date, tz=tz)
        if exp_date == self.get_default_date():
            dc_terms = "start={}; scheme=W3C-DTF".format(available_date_str)
            result = dc_terms
        else:
            result = "start={}; end={}; scheme=W3C-DTF".format(
                available_date_str, exp_date.isoformat())

        return result

    def get_reference_date(self, container):
        # Prefer precomputed, fall back to metadata
        ref_date = container.reference_date
        if not ref_date:
            ref_date = container.get_reference_date()

        return ref_date

    def get_time_in_seconds(self, time_str):
        try:
            time_list = time_str.split(':')
            total_seconds = 0
            if len(time_list) >= 1:
                for i, time_item in enumerate(time_list):
                    if time_item.isdigit():
                        if i == 0:
                            total_seconds = int(time_item) * 3600
                        elif i == 1:
                            total_seconds += int(time_item) * 60
                        else:
                            total_seconds += int(time_item)
                    else:
                        pass
                return str(total_seconds)
            else:
                return '0'
        except ValueError:
            return '0'

    def get_cuepoints(self, time_str):
        cuepoints_list = time_str.strip().split(",")
        cuepoints_string = '0'
        for time_str in cuepoints_list:   
            cuepoints_string += ',' + self.get_time_in_seconds(time_str)

        return cuepoints_string
