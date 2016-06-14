#!/usr/bin/env python
import web, os.path, logging, re, urlparse, sys, json, requests, time
from export import export_generator, list_node_dates
sys.path.append("..")
from waggle_protocol.utilities.mysql import *
# container
# docker run -it --name=beehive-api --link beehive-cassandra:cassandra --net beehive --rm -p 8183:80 waggle/beehive-server /usr/lib/waggle/beehive-server/scripts/apiserver.py 
# optional: -v ${DATA}/export:/export

LOG_FORMAT='%(asctime)s - %(name)s - %(levelname)s - line=%(lineno)d - %(message)s'
formatter = logging.Formatter(LOG_FORMAT)

handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)

logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

logging.getLogger('export').setLevel(logging.DEBUG)


port = 80
api_url_internal = 'http://localhost'
api_url = 'http://beehive1.mcs.anl.gov'

# modify /etc/hosts/: 127.0.0.1	localhost beehive1.mcs.anl.gov

web.config.log_toprint = True


def read_file( str ):
    print "read_file: "+str
    if not os.path.isfile(str) :
        return ""
    with open(str,'r') as file_:
        return file_.read().strip()
    return ""


# TODO
# show API calls on the web pages !


urls = (
    '/api/1/nodes/(.+)/latest',     'api_nodes_latest',
    '/api/1/nodes/(.+)/export',     'api_export',
    '/api/1/nodes/(.+)/dates',      'api_dates',
    '/api/1/nodes/?',               'api_nodes',
    '/api/1/epoch',                 'api_epoch',
#   '/',                            'index'
)

app = web.application(urls, globals())


def html_header(title):
    header= '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{0}</title>
</head>
<body>
'''
    return header.format(title)
 
def html_footer():
    return '''
</body>
</html>
'''


def internalerror(e):
    
    message = html_header("Error") + "Sorry, there was an error:<br>\n<pre>\n"+str(e) +"</pre>\n"+ html_footer()
    
    return web.internalerror(message)
    

def get_mysql_db():
    return Mysql( host="beehive-mysql",    
                    user="waggle",       
                    passwd="waggle",  
                    db="waggle")



class api_epoch:
    """
    Epoch time in seconds.
    """

    def GET(self):
        logger.debug('GET api_epoch')

        try:
            epoch= int(time.time())
        except:
            raise internalerror('error getting server time')
            
            
            
        return '{"epoch": %d}' % (epoch)


class api_nodes:        
    def GET(self):
        logger.debug('GET api_nodes')
        #query = web.ctx.query
        
        
        #web.header('Content-type','text/plain')
        #web.header('Transfer-Encoding','chunked')
        
        db = get_mysql_db()
        
        all_nodes = {}
        mysql_nodes_result = db.query_all("SELECT node_id,hostname,project,description,reverse_ssh_port FROM nodes;")
        for result in mysql_nodes_result:
            node_id, hostname, project, description, reverse_ssh_port = result
            
            if node_id:
                node_id = node_id.encode('ascii','replace').lower()
            else:
                node_id = 'unknown'
                
            if hostname:
                hostname = hostname.encode('ascii','replace')
                
            if description:
                description = description.encode('ascii','replace')
                
            
            
            logger.debug('got from mysql: %s %s %s %s %s' % (node_id, hostname, project, description, reverse_ssh_port))
            all_nodes[node_id] = {  'hostname'          : hostname,
                                    'project'           : project, 
                                    'description'       : description ,
                                    'reverse_ssh_port'  : reverse_ssh_port }
            
        
        
        nodes_dict = list_node_dates() # lower case
        
        for node_id in nodes_dict.keys():
            if not node_id in all_nodes:
                all_nodes[node_id]={}
        
        #for node_id in all_nodes.keys():
        #    logger.debug("%s %s" % (node_id, type(node_id)))
        
        obj = {}
        obj['data'] = all_nodes
        
        return  json.dumps(obj, indent=4)
        
            
class api_dates:        
    def GET(self, node_id):
        logger.debug('GET api_dates')
        
        node_id = node_id.lower()
        
        query = web.ctx.query
        
        nodes_dict = list_node_dates()
        
        if not node_id in nodes_dict:
            logger.debug("node_id not found in nodes_dict: " + node_id)
            raise web.notfound()
        
        dates = nodes_dict[node_id]
        
        logger.debug("dates: " + str(dates))
        
        obj = {}
        obj['data'] = sorted(dates, reverse=True)
        
        return json.dumps(obj, indent=4)
        
        
        
                        

class api_nodes_latest:        
    def GET(self, node_id):
        logger.debug('GET api_nodes_latest')
        
        query = web.ctx.query
        
        
        web.header('Content-type','text/plain')
        web.header('Transfer-Encoding','chunked')
        
        #for row in export_generator(node_id, '', True, ';'):
        #    yield row+"\n"
        yield "not implemented"



class api_export:        
    def GET(self, node_id):
        
        logger.debug('GET api_export')
        
        web.header('Content-type','text/plain')
        web.header('Transfer-Encoding','chunked')
        
        query = web.ctx.query.encode('ascii', 'ignore') #get rid of unicode
        if query:
            query = query[1:]
        #TODO parse query
        logger.info("query: %s", query)
        query_dict = urlparse.parse_qs(query)
        
        try:
            date_array = query_dict['date']
        except KeyError:
            logger.warning("date key not found")
            raise web.notfound()
        
        if len(date_array) == 0:
            logger.warning("date_array empty")
            raise web.notfound()
        date = date_array[0]
            
        logger.info("date: %s", str(date))
        if date:
            r = re.compile('\d{4}-\d{1,2}-\d{1,2}')
            if r.match(date):
                logger.info("accepted date: %s" %(date))
    
                num_lines = 0
                for row in export_generator(node_id, date, False, ';'):
                    yield row+"\n"
                    num_lines += 1
                
                if num_lines == 0:
                    raise web.notfound()
                else:
                    yield "# %d results" % (num_lines)
            else:
                logger.warning("date format not correct")
                raise web.notfound()
        else:
            logger.warning("date is empty")
            raise web.notfound()

if __name__ == "__main__":
    
    
    
    web.httpserver.runsimple(app.wsgifunc(), ("0.0.0.0", port))
    app.internalerror = internalerror
    app.run()



