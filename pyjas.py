#!/usr/bin/env python

#Code by Abinash Sahu

import time
import Queue
import threading
import re
import mechanize
import os
import sys
import webbrowser
import urllib2
import pickle

nodes_to_visit=Queue.Queue()
visited_nodes=[]
max_num_threads=6
node_dict={} #Contains ip-name mapping of nodes in network with ip as key
full_list=[] #Contains list of all links

def check_or_make(folder_path):
    """Check if provided folder exists at the specified location
    otherwise create it there.
    """
    
    curr_directory=os.getcwd()	
    for folder in folder_path.split(os.sep):
        if os.path.isdir(folder):
            os.chdir(folder)            
        else:
            os.mkdir(folder)
            os.chdir(folder)
    os.chdir(curr_directory)
    return

class NE:
    def __init__(self, ip):
        self.ip=ip
        self.neighbours=[]
        self.laser_ports={}

        self.baseurl='http://%s:20080/' % (self.ip)

        try:
            br=mechanize.Browser()                                  #Create nechanize browser object
            br.add_password(self.baseurl, username, passw)		    #Get user id and password from command line arguements
            page=br.open(self.baseurl, timeout=10.0).read()		    #Check if NE is accessible
            if 'alarmBanner' in page:
                print "Logged in to %s" % (self.baseurl)

            self.get_laser_data(br)									#Read laser data of STM ports
            if(self.add_neighbours(br)):
                self.backup(br)										#Backup cross-connect info
        except:
            print "\tError reading "+ip
        br.close()
        return(None)

    def add_neighbours(self, br):
        """Goes through the list of IPs  listed as neighbours (please 
        keep auto-discover switched ON) and copies their state, IP & STM
        port number.
        """
        
        #Regex patterns
        name_pattern=r'\-(\S+.*?)\('
        row_pattern=r'<b>Trunk.*[\n]+.*?<SEL'
        ip_status_pattern=r'</A> </TH><TD >([\S]+).*?</TD><TD >.*?\d+(?:[\d\.]+){3}.*?(\d+(?:[\d\.]+){3}).*?</TD>'
        stm_pattern=r'<TD >(\d+\-\d+\-\d+\s)</TD>'
        
        nbr_ne_status=br.open(self.baseurl+'EMSRequest/ViewTrunk', timeout=10.0).read().rstrip()
        try:
            self.name=re.findall(name_pattern, nbr_ne_status)[0]
            self.name=re.sub('[^\s!-~]', ' ', self.name)

        except:
            print("\tError getting name for %s"%(self.baseurl))
            return()
            
        node_dict[self.ip]=self.name
        for srch in re.findall(row_pattern,nbr_ne_status):
            match=re.search(ip_status_pattern, srch)
            if match:
                status=str(match.group(1))
                ip=match.group(2)
                stm=str(re.search(stm_pattern, srch).group(1)).strip()
                try:
                    full_list.append([self.ip,ip,status, self.laser_ports[stm]])
                    #print self.laser_ports[stm]
                    self.neighbours.append([ip,status.upper(), self.laser_ports[stm]])
                except:
                    return()
                    #print self.laser_ports, ip, status.upper(), stm
        return(self.name)

    def tell(self):
        """For debugging only """
        return(self.name, self.neighbours)

    def backup(self, br):
        """Saves the node's cross-connects in another HTML file. Will replace
        the last recorded cross-connect saved on the current day. That is to
        say running first time on Wednesday will NOT overwrite Tuesday's data 
        but running another time on Wednesday WILL overwrite the first 
        cross-connect backup of Wednesday.
        """
        
        try:
            configs=br.open(self.baseurl+'EMSRequest/ViewConnections', timeout=10.0).read()
            start_copy=configs.find('<CAPTION><B>Cross')
            configs=configs[start_copy:-1]
            time_backup=str(time.strftime("%H:%M:%S  %d/%m/%y")+":\n\n")
            backup_head="<HTML>\n<TITLE> Cross-connect backup of "+self.name+" taken on "+time_backup+"</TITLE>\n</HEAD>"
            backup_table_line='<TABLE  BORDER="1" CELLPADDING="0" CELLSPACING="0" WIDTH="60%" STYLE="background-color: #AAAAAA">'
            backup_body="<BODY><B><FONT COLOR='RED'>Cross-connect backup of "+self.name+" taken on "+time_backup+"</B></FONT>"
            backup_folder="logs"+os.sep+"backup"+os.sep+time.ctime()[0:3]
            check_or_make(backup_folder)
            filename=str(os.getcwd()+os.sep+backup_folder+os.sep+str(self.name)+".html")
            with open (filename, 'w') as bkpconfig:
                bkpconfig.write(backup_head+backup_body+backup_table_line+configs)
            print("Config file for "+str(self.name)+" written to disk.")
        except:
            print("Error getting config info for "+str(self.ip))
        return()

    def get_laser_data(self, br):
        """Reads the received laser power from different STM ports and 
        records them against the ports.
        """
        
        laser_pattern=r'<TD >STM\d+\-(\d.*?)</TD>.*?([\-\d].*?)</TD><TD >'
        
        try:
            laser_stat_page=br.open(self.baseurl+'EMSRequest/Laser?Submit=View', timeout=10.0).read()
            
            for srch in re.findall(laser_pattern, laser_stat_page):
                stm=str(srch[0]).strip()
                laser_power=str(srch[1]).strip()
                self.laser_ports[stm]=laser_power
        except:
            print "Error reading laser data for "+self.baseurl
            return(None)
        return()

    def check_online(self, url):
        #For future use :P
        try:
            code=urllib2.urlopen(url, timeout=2).getcode()
        except urllib2.HTTPError as e:
            code=e.code
        except urllib2.URLError:
            code=0
        if code==401 or code==200:
            return True
        
        return False

def get_node(node_queue, prev_node):
    """Gets a node from the Queue to process and spawn new threads
    if required."""
    
    th_count=1
    
    current_node=node_queue.get()
    #ret_str="Getting data for "+(str(current_node))+" came from "+str(prev_node)
    #print(ret_str)
    if not (current_node in visited_nodes):
        visited_nodes.append(current_node)
        node=NE(current_node)
        if(node.neighbours):
            for neighbour in node.neighbours:
                if not(neighbour[0] in visited_nodes):
                    node_queue.put(neighbour[0])
                    th_count+=1
        for i in range(th_count):
            th=threading.Thread(target=get_node, args=(node_queue,current_node, ))
            th.setDaemon(True)
            th.start()
    node_queue.task_done()
    #print('Task Done')
    #exit()
    return()

def make_legend(filename):
    """Uses the IP Cache file to store/retrieve IP <> Name mappings. If 
    the cache file exists opens it and updates else creates with the 
    available data."""
    
    wrk_dir=os.path.split(filename)
    if os.path.isfile(wrk_dir[0]+os.sep+'ipcache.tmp'):
        ip_file=open(wrk_dir[0]+os.sep+'ipcache.tmp', 'r')
        ip_dict=pickle.load(ip_file)
        ip_file.close()
        for element in node_dict.keys():
            if not(element in ip_dict.keys()):
                ip_dict[element]=node_dict[element]
    else:
        ip_dict=node_dict
    ip_file=open(wrk_dir[0]+os.sep+'ipcache.tmp', 'w')
    pickle.dump(ip_dict, ip_file)
    ip_file.close()
    return(ip_dict)

def make_html(ne_list, filename, start_time):
    """Save the report as a HTML file"""
    
    #Keep list of inaccessible nodes
    na_nodes=[]
    
    #ne_list contains link status of all nodes
    for item in ne_list:
        #Use node names if available else use IP
        try:
            item[0]=node_dict[item[0]]  #Source
            item[1]=node_dict[item[1]]  #Destination
        except:
            pass
    
    #Prepare the HTML file
    with open(filename, 'w') as htmlfile:
        file_time=str(time.strftime("%H:%M:%S  %d/%m/%y"))
        htmlfile.write('<!DOCTYPE html>\n<HTML>\n<HEAD>\n\t<TITLE>Route Status on '+file_time+'</TITLE>')
        cssStyles='''\n\t<STYLE TYPE="TEXT/CSS">
                    a{
                        text-decoration:none;
                        color:black;
                    }
                    a:hover{
                        background-color:#FFF380;
                    }
                    #data tbody tr:hover{
						background-color:#FFF380;
					}
                    .notavailable{
                        background-color: #F75D59;
                        color: #FFFFFF;
                        }
                    .available{
                        background-color: #4CC417;
                        color: #FFFFFF;
                    }
                    .statusUp{
                        color: green;
                        text-align: center;
                    }
                    .statusDown{
                        color: red;
                        text-align: center;
                    }
                    .powerDown{
                        color: red;
                        text-align: center;
                    }
                    .powerRisky{
                        color: orange;
                        text-align: center;
                    }
                    .powerNormal{
                        color: blue;
                        text-align: center;
                    }
                    .nodeDown{
                        background-color: red;
                        color: white;
                        font-weight: bold;
                        text-align: center;                        
                    }
                </STYLE>
                '''
        htmlfile.write(cssStyles)
        htmlfile.write("\n</HEAD>\n<BODY>\nThe status as on "+file_time+":\n\n<BR><BR>\n")
        htmlfile.write("<TABLE BORDER=1 ID='data'>\n<THEAD>\t\n<TR>\n\t<TH>DESTINATION</TH>\n\t<TH>SOURCE</TH>\n\t<TH>STATUS</TH>\n\t<TH>POWER LEVEL (dBm)</TH>\n\t</TR>\n</THEAD>\n<TBODY>\n")
        for row in ne_list:
            
            #Status formatting
            if 'Down' in str(row[2]):
                status_format='statusDown">'
            else:
                status_format='statusUp">'
            
            #Power formatting
            if float(str(row[3]))<-34.99:
                power_format='powerDown">'
            elif float(str(row[3]))>-34.99 and float(str(row[3]))<-30.0:
                power_format='powerRisky">'
            else:
                power_format='powerNormal">'
            
            #Row[0] = DEST, Row[1] = SOURCE, Row[2] = STATUS & Row[3] = power
            #If received power is -99 and only IP address in source name
            #put node in not reachable list & highlight row
            
            if float(str(row[3]))==-99 and re.match(r'[\d]+.[\d]+.', row[1]):
                na_nodes.append(str(row[1]))
                status_format='nodeDown">'
                power_format='nodeDown">'
            
            #Node is reachable but link is down - highlight row
            if float(str(row[3]))==-99 and 'Down' in str(row[2]):
                status_format='nodeDown">'
                power_format='nodeDown">'
                
            htmlfile.write('<TR>\n\t<TD>'+str(row[0])+'</TD>\n\t<TD>'+str(row[1])+
                           '</TD>\n\t<TD CLASS="'+status_format+str(row[2])+
                           '</TD>\n\t<TD CLASS="'+power_format+str(row[3])+'</TD>\n</TR>\n')
        htmlfile.write("\n</TBODY>\n</TABLE>\n<br>")

        #Make legend section
        ip_dict=make_legend(filename)
        htmlfile.write('<BR>\n'*2)
        legend_col=3
        htmlfile.write('\n<B>IP to Name (from memory):</B><BR>\n')
        htmlfile.write('<TABLE BORDER=1><TR>\n'+'\n\t<TH>IP ADD</TH>\n\t<TH>NE NAME</TH>'*legend_col+'\n</TR>')
        fmt_count=0
        htmlfile.write('\n<TR>')
        for ip_add in sorted(ip_dict.keys()):
            if fmt_count%legend_col==legend_col-1:
                fmt_cntr=1
                fmt_count=0
            else:
                fmt_cntr=0
                fmt_count+=1
            
            if str(ip_add) in na_nodes:
                legend_ip_fmt='notavailable">'
            else:
                legend_ip_fmt='available">'
            
            htmlfile.write('\n\t<TD CLASS="'+legend_ip_fmt+str(ip_add)+'</TD>\n\t<TD><A HREF="backup'+os.sep+time.ctime()[0:3]+os.sep+str(ip_dict[ip_add])+'.html">'+str(ip_dict[ip_add])+'</A></TD>'+'\n</TR>\n<TR>'*fmt_cntr)

        htmlfile.write('\n</TR>\n</TABLE><BR>\n\n')
        
        htmlfile.write("\n<BR> Visited "+str(len(node_dict.keys()))+" nodes in "+(str(time.time()-start_time))+" seconds.")
        htmlfile.write('\n\n<!--Scripted by Abinash Sahu-->')
        htmlfile.write('\n<br><br>Script sourced from <a href="https://github.com/abinash111/pyjas">The Pyjas project</a>')
        htmlfile.write('\n</BODY>\n</HTML>')
    
    #Display the report in the default browser
    webbrowser.open_new_tab(filename)
    return()


if __name__=='__main__':
    global username, passw
    
    #Create the 'logs' folder if it doesn't exist
    check_or_make("logs")
    
    #This is the file name we are going to store the report with
    filename=str(os.getcwd()+os.sep+'logs'+os.sep+str(time.strftime("%d%m%y%H%M%S"))+".html")
    
    #Just for the stats
    start_time=time.time()
    
    #Check if all necessary parameters have been provided
    if len(sys.argv)>3:
        start_ip=str(sys.argv[1])
        username=str(sys.argv[2])
        passw=str(sys.argv[3])
    else:
        print('Missing/invalid parameters. Exiting.')
        raw_input()
        sys.exit()
    
    #Initialize the queue
    nodes_to_visit.put(start_ip)
    
    #create_threads(max_num_threads, nodes_to_visit)
    get_node(nodes_to_visit, 'START')
    
    #wait till all threads finished working
    nodes_to_visit.join()
    
    if len(full_list)>1:
        print("Writing to file...")
        make_html(full_list, filename, start_time)
        print("Log recorded to "+filename+".")
    else:
        print("ERROR : Check LAN connection/settings")
    print("Press ENTER to close this window")

    raw_input()
    exit()
