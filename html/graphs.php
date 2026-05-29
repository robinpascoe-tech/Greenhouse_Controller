<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<?php
  $bg = array('greenhousebg4.jpg', 'greenhousebg5.jpg', 'greenhousebg6.jpg', 'greenhousebg7.jpg', 'greenhousebg8.jpg', 'greenhousebg9.jpg', 'greenhousebg10.jpg', 'greenhousebg11.jpg', 'greenhousebg12.jpg', 'greenhousebg13.jpg' ); // array of filenames

  $i = rand(0, count($bg)-1); // generate random number size of the array
  $selectedBg = "$bg[$i]"; // set variable equal to which random filename was chosen
?>
<head>
<meta content="en-ca" http-equiv="Content-Language">
<meta content="text/html; charset=utf-8" http-equiv="Content-Type">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greenhouse Graphs</title>
<link rel="shortcut icon" type="image/x-icon" href="images/greenhouseicon.ico">
<style type="text/css">
<!--
body{
background: url(images/<?php echo $selectedBg; ?>) no-repeat;
}
-->
</style>
<link rel='stylesheet' type='text/css' href='css/style.css' />
<link id="size-stylesheet" rel='stylesheet' type='text/css' href='css/narrow.css' />
<script type='text/javascript' src='js/resolution-test.js'></script>
<body>
<div class="wrap" id="moreinfo">
<table style="width: 300px" align="center">
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="tempgraphs.php"><img alt="Temp Graphs" height="100" src="images/thermometer.png" width="100"><br>Temp Graphs</a><br><br></td>
		<td class="auto-style9" style="width: 199px"><br><a href="tempgraphsf.php"><img alt="Temp F Graphs" height="100" src="images/thermometerf.png" width="100"><br>Fahrenheit Graphs</a><br><br></td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="humiditygraphs.php"><img alt="Humidity Graphs" height="100" src="images/humidity.png" width="100"><br>Humidity Graphs</a><br><br></td>
		<td class="auto-style9" style="width: 199px"><br><a href="operationsgraphs.php"><img alt="Operations Graphs" height="100" src="images/operations.png" width="100"><br>Operations Graphs</a><br><br></td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="combinedopsgraphs.php"><img alt="Combined Graphs" height="100" src="images/operations.png" width="100"><br>Combined Graphs</a><br><br></td>
		<td class="auto-style9" style="width: 199px">&nbsp;</td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"><br><a href="index.php"><img alt="Home" height="100" src="images/greenhousehome.png" width="100"><br>Home</a><br><br></td>
		<td class="auto-style9" style="width: 199px"><br><a href="/cacti/graph_view.php"><img alt="Temp Graphs" height="100" src="images/chart01.png" width="100"><br>More Graphs</a><br><br></td>
	</tr>
</table>
</div>
</body>
</html>
