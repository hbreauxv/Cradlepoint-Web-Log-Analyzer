$(document).ready(function(){
    //connect to the socket server.
    var socket = io.connect('http://' + document.domain + ':' + location.port + '/')

    socket.on('plots', function(msg){
        console.log("Got plots")
        console.log(msg)
    });
});