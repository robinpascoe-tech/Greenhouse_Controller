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
<title>Greenhouse</title>
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
<script type="text/javascript" src="/jquery/jquery.min.js"></script>
<script type='text/javascript' src='js/resolution-test.js'></script>
<script src="../amcharts2/amcharts.js" type="text/javascript"></script>
<script src="../amcharts2/gauge.js" type="text/javascript"></script>
<script>
			var chartavgtemp;
			var arrowavgtemp;
			var axisavgtempC;
			var axisavgtempF;		

			var chartoutsidetemp;
			var arrowoutsidetemp;
			var axisoutsidetempC;
			var axisoutsidetempF;			
			
			AmCharts.ready(function () {

// Avg Indoor Temp Graph
				// create angular gauge
				chartavgtemp = new AmCharts.AmAngularGauge();
				chartavgtemp.radius = "45%";
				chartavgtemp.addTitle("Inside Temperature");
				chartavgtemp.panEventsEnabled = false;


				// kilometers axis
				axisavgtempC = new AmCharts.GaugeAxis();
				axisavgtempC.startValue = 0;
				axisavgtempC.endValue = 50;
				axisavgtempC.radius = "100%";
				axisavgtempC.inside = false;
				axisavgtempC.gridInside = false;
				axisavgtempC.axisColor = "#94dca0";
				axisavgtempC.tickColor = "#94dca0";
				axisavgtempC.axisThickness = 1;
				axisavgtempC.valueInterval = 5;
				// bottom text
                axisavgtempC.bottomTextYOffset = -25;
				chartavgtemp.addAxis(axisavgtempC);
				
                // color bands
                var band1 = new AmCharts.GaugeBand();
                band1.startValue = 12;
                band1.endValue = 35;
                band1.color = "#00CC00";

                var band2 = new AmCharts.GaugeBand();
                band2.startValue = 8;
                band2.endValue = 12;
                band2.color = "#ffac29";

                var band3 = new AmCharts.GaugeBand();
                band3.startValue = 0;
                band3.endValue = 8;
                band3.color = "#ea3838";
				
				var band4 = new AmCharts.GaugeBand();
                band4.startValue = 35;
                band4.endValue = 40;
                band4.color = "#ffac29";
				
				var band5 = new AmCharts.GaugeBand();
                band5.startValue = 40;
                band5.endValue = 50;
                band5.color = "#ea3838";
                
                axisavgtempC.bands = [band1, band2, band3, band4, band5];

				// miles axis
				axisavgtempF = new AmCharts.GaugeAxis();
				axisavgtempF.startValue = 32;
				axisavgtempF.endValue = 122;
				axisavgtempF.radius = "80%";
				axisavgtempF.axisColor = "#bebd61";
				axisavgtempF.tickColor = "#bebd61";
				axisavgtempF.axisThickness = 1;
				axisavgtempF.valueInterval = 9;
				// bottom text
                axisavgtempF.bottomTextYOffset = -30;
				chartavgtemp.addAxis(axisavgtempF);

				// arrow
				arrowavgtemp = new AmCharts.GaugeArrow();
				arrowavgtemp.radius = "85%";
				arrowavgtemp.color = "#8ec487";
				arrowavgtemp.innerRadius = 20;
				arrowavgtemp.nailRadius = 0;
				chartavgtemp.addArrow(arrowavgtemp);

	//Outside Temp Chart
				// create angular gauge
				chartoutsidetemp = new AmCharts.AmAngularGauge();
				chartoutsidetemp.radius = "45%";
				chartoutsidetemp.addTitle("Outside Temperature");
				chartoutsidetemp.panEventsEnabled = false;

				// kilometers axis
				axisoutsidetempC = new AmCharts.GaugeAxis();
				axisoutsidetempC.startValue = -5;
				axisoutsidetempC.endValue = 45;
				axisoutsidetempC.radius = "100%";
				axisoutsidetempC.inside = false;
				axisoutsidetempC.gridInside = false;
				axisoutsidetempC.axisColor = "#94dca0";
				axisoutsidetempC.tickColor = "#94dca0";
				axisoutsidetempC.axisThickness = 1;
				axisoutsidetempC.valueInterval = 5;
				// bottom text
                axisoutsidetempC.bottomTextYOffset = -25;
				chartoutsidetemp.addAxis(axisoutsidetempC);
				
                // color bands
                var band1outside = new AmCharts.GaugeBand();
                band1outside.startValue = 12;
                band1outside.endValue = 35;
                band1outside.color = "#00CC00";

                var band2outside = new AmCharts.GaugeBand();
                band2outside.startValue = 8;
                band2outside.endValue = 12;
                band2outside.color = "#ffac29";

                var band3outside = new AmCharts.GaugeBand();
                band3outside.startValue = 0;
                band3outside.endValue = 8;
                band3outside.color = "#ea3838";
				
				var band4outside = new AmCharts.GaugeBand();
                band4outside.startValue = 35;
                band4outside.endValue = 40;
                band4outside.color = "#ffac29";
				
				var band5outside = new AmCharts.GaugeBand();
                band5outside.startValue = 40;
                band5outside.endValue = 45;
                band5outside.color = "#ea3838";

				var band6outside = new AmCharts.GaugeBand();
                band6outside.startValue = -5;
                band6outside.endValue = 0;
                band6outside.color = "#0000cc";
                
                axisoutsidetempC.bands = [band1outside, band2outside, band3outside, band4outside, band5outside, band6outside];

				// miles axis
				axisoutsidetempF = new AmCharts.GaugeAxis();
				axisoutsidetempF.startValue = 23;
				axisoutsidetempF.endValue = 113;
				axisoutsidetempF.radius = "80%";
				axisoutsidetempF.axisColor = "#bebd61";
				axisoutsidetempF.tickColor = "#bebd61";
				axisoutsidetempF.axisThickness = 1;
				axisoutsidetempF.valueInterval = 9;
				// bottom text
                axisoutsidetempF.bottomTextYOffset = -30;
				chartoutsidetemp.addAxis(axisoutsidetempF);

				// arrow
				arrowoutsidetemp = new AmCharts.GaugeArrow();
				arrowoutsidetemp.radius = "85%";
				arrowoutsidetemp.color = "#8ec487";
				arrowoutsidetemp.innerRadius = 20;
				arrowoutsidetemp.nailRadius = 0;
				chartoutsidetemp.addArrow(arrowoutsidetemp);
				
//write charts				

				chartavgtemp.write("chartavgtempdiv");
				chartoutsidetemp.write("chartoutsidetempdiv");
                // change value every 5 seconds
                setInterval(updateTemps, 5000);
   
				
			});
			
			
            // set random value
            function updateTemps() {
				var data = {
				"action": "test"
				};
				data = $(this).serialize() + "&" + $.param(data);
				$.ajax({
				type: "POST",
				dataType: "json",
				url: "gettemps.php", //Relative or absolute path to response.php file
				data: data,
				success: function(data) {
					arrowavgtemp.setValue(data[0]);
					axisavgtempC.setBottomText(data[0] + " \xB0C");
					axisavgtempF.setBottomText(data[1] + " \xB0F");
					arrowoutsidetemp.setValue(data[2]);
					axisoutsidetempC.setBottomText(data[2] + " \xB0C");
					axisoutsidetempF.setBottomText(data[3] + " \xB0F");
      			}
				});
			}
			
        </script>
<script type="text/javascript">
function cancelfanoverride() {
    $.get("cancelfanoverride.php");
    return false;
}
function cancelwindowoverride() {
    $.get("cancelwindowoverride.php");
    return false;
}
</script>
</head>
<body>

<script type="text/javascript" language="javascript"> 
jQuery(document).ready(function ($) { /// Wait till page is loaded
    $('#wrap').load('indexcontent.php', function() {
		startActivityRefresh();
	});
});
</script>

<script type="text/javascript" language="javascript"> 
var timer;
var seconds = 5; // how often should we refresh the DIV?

function startActivityRefresh() {
    timer = setInterval(function() {
        $.ajaxSetup({ cache: false });
		$('#wrap').load('indexcontent.php');
    }, seconds*1000)
}

function cancelActivityRefresh() {
    clearInterval(timer);
}
</script>
<div id="pagewrap">
<div id="floatcontainer">
<div class="gauges" id="chartavgtempdiv"></div>
<div class="gauges" id="chartoutsidetempdiv"></div>
</div>
<div class="wrap" id="moreinfo">
<table style="width: 300px" align="center">
	<tr>
		<td class="auto-style9" style="width: 199px"><a href="temperatures.php"><img alt="Thermometer" height="100" src="images/thermometer.png" width="100"><br>Temps</a><br>
	<br></td>
		<td class="auto-style9" style="width: 199px"><a href="graphs.php"><img alt="Graphs" height="100" src="images/chart01.png" width="100"><br>Graphs</a><br>
	<br></td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"><a href="webcam.php"><img alt="Webcam" height="100" src="images/webcam.png" width="100"><br>Webcams</a></td>
		<td class="auto-style9" style="width: 199px"</td>
	</tr>
</table>
</div>
<div class="wrap" id="wrap">

</div>
</div>
</body>
</html>