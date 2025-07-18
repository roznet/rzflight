#!/bin/zsh
#

SRC_DIR=cache
DST_DIR=../euro_aip/example/cache/autoroutersource

function cp_procedures {
	for file in $SRC_DIR/procedures/*json; do
	    if [[ -f $file ]]; then
		filename=$(basename "$file")
		dest_file="$DST_DIR/procedures_${filename}"
		echo "Copying $filename to $dest_file"
		cp $file $dest_file
	    fi
	done
}

function cp_pdfs {
	for file in $SRC_DIR/docs/*pdf; do
	    if [[ -f $file ]]; then
		filename=$(basename "$file")
		# extract ICAO from the name of the form XX_AD_2_EDSB_en.pdf
		# This regex looks for 4 uppercase letters surrounded by underscores
		icao=$(echo $filename | sed -n 's/.*_2_\([A-Z]\{4\}\)_[eE][nN].*/\1/p')
		# if the ICAO is found, copy the file to the destination directory
		if [[ -n "$icao" ]]; then
			dest_file="$DST_DIR/document_${icao}.pdf"
			echo "Copying $filename to $dest_file"
			cp $file $dest_file
		else
		    echo "No ICAO found in filename: $filename"
		fi	
	    fi
	done
}

function cp_airport_doclist  {
	for file in $SRC_DIR/airport/*json; do
	    if [[ -f $file ]]; then
		filename=$(basename "$file")
		dest_file="$DST_DIR/airport_doclist_${filename}"
		echo "Copying $filename to $dest_file"
		cp $file $dest_file
	    fi
	done
}

cp_airport_doclist

#cp_pdfs
