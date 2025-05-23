import collections
import cProfile
import os
import re
import requests
import glob
from bs4 import BeautifulSoup

class Node:
    def __init__(self, identifier, parent=None):
        self.__identifier = identifier
        self.__children = []
        self.__parent = parent

    @property
    def identifier(self):
        return self.__identifier

    @property
    def children(self):
        return self.__children
        
    @property
    def parent(self):
        return self.__parent

    def add_child(self, identifier):
        self.__children.append(identifier)

class Tree:
    def __init__(self):
        self.__nodes = {}

    @property
    def nodes(self):
        return self.__nodes

    def add_node(self, identifier, parent=None):
        if parent is not None:
            if parent not in self.__nodes:
                self.add_node(parent)  # Add parent if it doesn't exist
            node = Node(identifier, self.__nodes[parent])
        else:
            node = Node(identifier)
        self[identifier] = node

        if parent is not None:
            self[parent].add_child(identifier)

        return node

    def display(self, identifier, depth=0):
        children = self[identifier].children
        if depth == 0:
            print(identifier)
        else:
            print("\t" * depth + str(identifier))

        depth += 1
        for child in children:
            self.display(child, depth)  # recursive call

    def traverse(self, identifier, mode="depth"):
        yield self.__nodes[identifier]
        queue = self[identifier].children
        while queue:
            yield self.__nodes[queue[0]]
            expansion = self[queue[0]].children
            if mode == "depth":
                queue = expansion + queue[1:]  # dfs
            elif mode == "breadth":
                queue = queue[1:] + expansion  # bfs

    def __getitem__(self, key):
        return self.__nodes[key]

    def __setitem__(self, key, item):
        self.__nodes[key] = item

def createSoup(file_path):
    with open(file_path, "r", encoding="utf8") as myfile:
        html = myfile.read()
    soup = BeautifulSoup(html, 'html.parser')
    return soup

def getChildren(theNode, level):
    children = []
    
    theChildren = theNode.findAll('dl')
    for child in theChildren:
        parents = len(child.findParents('dl'))
        header = child.findPrevious('h3')
        if parents == level + 1:
            children.append(str(''.join(header.findAll(string=True))))
    return children

def genHeaderTree(file_path, theSoup):
    iterSoup = theSoup.findAll('dl')
    
    if "chrome" in file_path or "firefox" in file_path: 
        headerList = theSoup.findAll('h3')
        iterSoup = iterSoup[1:]
    else:
        headerList = theSoup.findAll(re.compile("h?"))
    
    firstHeader = str(headerList[0].text)
    
    headerTree = Tree()
    headerTree.add_node(firstHeader)
    
    for item in iterSoup:
        parents = len(item.findParents('dl'))
        children = getChildren(item, parents)
        if children:
            for child in children:
                if "chrome" in file_path or "firefox" in file_path:
                    parent = str(item.findPrevious('h3').text)
                else:
                    parent = str(item.findPrevious(re.compile("h?")).text)
                headerTree.add_node(child, parent)
    return headerTree

def printHeaderList(file_path, theTree, theSoup, linkList):
    if "chrome" in file_path or "firefox" in file_path: 
        headerList = theSoup.findAll('h3')
    else:
        headerList = theSoup.findAll(re.compile("h?"))    
    
    firstHeader = ''.join(headerList[0].findAll(text=True))
    
    iterTree = theTree.traverse(firstHeader, "depth")
    
    removed = 0    
    if "chrome" in file_path or "firefox" in file_path or "ie" in file_path:
        next(iterTree)  # Remove "Bookmarks Toolbar" or "Bookmarks"
        removed += 1
        
    for node in iterTree:
        temp = node
        parents = 0
        while temp.parent:
            parents += 1
            temp = temp.parent
        prepend = "\t" * (parents - removed)
        links = getLinks(file_path, theSoup, node.identifier)
        count = len(links)
        percentage = "{0:.2f}%".format(((count + 0.0)/len(linkList)) * 100)
        print((prepend + str(node.identifier) + " - " + 
            str(count) + " = " + percentage))

def getLinks(file_path, theSoup, header):
    s = None
    headerNodes = theSoup.findAll('h3')
    for node in headerNodes:
        if node.text == header:
            s = node
            break
    
    while getattr(s, 'name', None) != 'dl':
        if "chrome" in file_path or "ie" in file_path:
            s = s.nextSibling
        elif "firefox" in file_path:
            s = s.findNext('dl')
    return s.findAll('a')

def populateList(linkList, urlType):
    urlList = []
    
    for link in linkList:
        if urlType == "normal":
            urlList.append(str(link['href']))
        elif urlType == "noProtocol":
            noProtocol = link['href'].split('://', 1)[-1]
            urlList.append(str(noProtocol))
    return urlList

def getDupes(inList):        
    return [item for item, c in list(collections.Counter(inList).items()) if c > 1]

def checkStatus(link):
    resp = requests.head(link)
    return resp

def main():
    supportedBrowsers = ["chrome", "firefox", "ie"]
    bookmark_files = glob.glob("bookmarks*.html")
    
    getCount = True
    checkDupes = True
    checkErrors = False
    
    for file_path in bookmark_files:
        print(f"Processing file: {file_path}")
        
        mySoup = createSoup(file_path)
        linkList = mySoup.find_all('a')
        
        for link in linkList[:]:
            if link['href'].startswith('place'):
                linkList.remove(link)
                
        myTree = genHeaderTree(file_path, mySoup)
        
        if getCount:
            total = len(linkList)
            print("Total number of bookmarks: " + str(total) + "\n")

        if checkDupes:    
            if any(browser in file_path for browser in supportedBrowsers):
                printHeaderList(file_path, myTree, mySoup, linkList)

                urlList = populateList(linkList, "normal")    
                dupes = getDupes(urlList)
                print("\n\nDUPLICATE LINKS = " + str(len(dupes)))
                print("----------------")
                for dupe in dupes:
                    print(dupe)
            
                urlList = populateList(linkList, "noProtocol")    
                dupes = getDupes(urlList)    
                print("\nDUPLICATE LINKS (IGNORING PROTOCOL) = " + str(len(dupes)))
                print("------------------------------------")
                for dupe in dupes:
                    print(dupe)
        
        if checkErrors:
            print("\nERROR CONNECTS")
            print("---------------"    )
            for link in linkList:
                try:
                    response = checkStatus(link['href'])
                except:
                    print("ERROR?!")
                if response.status_code != 200:
                    print(str(response.status_code) + " - " + link['href'])

if __name__ == "__main__":
    main()
