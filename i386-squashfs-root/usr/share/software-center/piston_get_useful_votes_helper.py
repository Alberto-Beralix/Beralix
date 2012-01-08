#!/usr/bin/python

import pickle
import logging
import sys

from optparse import OptionParser
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from piston_mini_client import APIError

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # common options for optparse go here
    parser = OptionParser()

    # check options
    parser.add_option("--username", default=None)
    (options, args) = parser.parse_args()

    rnrclient = RatingsAndReviewsAPI()
            
    useful_votes = []
    
    if options.username:
        try:
            useful_votes = rnrclient.get_usefulness(username=options.username)
        except ValueError as e:
            LOG.error("failed to parse '%s'" % e.doc)
        except APIError, e:
            LOG.warn("_get_useful_votes_helper: no usefulness able to be retrieved for username: %s" % (options.username))
            LOG.debug("_get_reviews_threaded: no reviews able to be retrieved: %s" % e)
        except:
            LOG.exception("_get_useful_votes_helper")
            sys.exit(1)

    # print to stdout where its consumed by the parent
    try:
        print pickle.dumps(useful_votes)
    except IOError:
        # this can happen if the parent gets killed, no need to trigger
        # apport for this
        pass

