import Head from 'next/head';
import { DashboardLayout } from '../../../components/DashboardLayout';
import axios from 'axios'
import useSWR from "swr";
import {useEffect, useState} from "react";
import SearchBar from "../../../components/SearchBar";
import ResultList from "../../../components/schooladmin/result/ResultList";
import {Box, Container} from "@mui/material";
import NextNProgress from "nextjs-progressbar";
import AxiosInstance from "../../../utils/axiosInstance";

const Results = ({ resultList }) => {
    const [pageIndex, setPageIndex] = useState(1);
    const [searchText, setSearchText] = useState('')

    const [filter, setFilter] = useState(false);
    const [fromDate, setFromDate] = useState('');
    const [toDate, setToDate] = useState('');
    const [exportResultLoading, setExportResultLoading] = useState(false)

    const { data: results, mutate } = useSWR(`school/exam/student/results/?page=${pageIndex}&search=${searchText}${filter ? `&from=${fromDate}&to=${toDate}`: ''}`, {
        fallbackData: resultList,
        revalidateOnFocus: false,
    });

    const onClickExportCSV = async () => {
        await AxiosInstance.get(`school/export/csv/`).then(({data}) => {
            let link = `${process.env.api}/media/files/${data?.spreadsheetId}.csv`
            const a = document.createElement('a')
            a.target = "_blank"
            a.href = link
            a.download = link.split('/').pop()
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
        }).catch((_e) => {
            alert('Something went wrong.')
        })
    }

    const onClickExportResult = async () => {
        setExportResultLoading(true)
        let data = null
        if(filter){
            data = {
                'from': fromDate,
                'to': toDate,
            }
        }
        await AxiosInstance.put(`school/export/result/`, data).then(({data}) => {
            let link = `${process.env.api}/media/files/${data?.file_name}`
            const a = document.createElement('a')
            a.target = "_blank"
            a.href = link
            a.download = link.split('/').pop()
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            setExportResultLoading(false)
        }).catch((_e) => {
            alert('Something went wrong.')
            setExportResultLoading(false)
        })
    }

    useEffect(() => {
        mutate()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [resultList])

    const onKeyUpSearch = (e) => {
        if(e.code === 'Enter'){
            setSearchText(e.target.value)
            setPageIndex(1)
        }
    }

    const onChangeSearch = (e) => {
        if(e.target.value === ''){
            setSearchText('')
        }
    }

    return (
        <>
            <NextNProgress height={3}/>
            <Head>
                <title>
                    Results
                </title>
            </Head>
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                }}
            >
                <Container maxWidth={false}>
                    <SearchBar
                        onChange={onChangeSearch}
                        onKeyUp={onKeyUpSearch}
                        text={searchText}
                        setText={setSearchText}
                        hasQuery={false}
                    />
                    <Box sx={{ mt: 1 }}>
                        <ResultList
                            pageIndex={pageIndex}
                            setPageIndex={setPageIndex}
                            students={results}
                            fromDate={fromDate}
                            toDate={toDate}
                            setFromDate={setFromDate}
                            setToDate={setToDate}
                            filter={filter}
                            setFilter={setFilter}
                            onClickExportCSV={onClickExportCSV}
                            onClickExportResult={onClickExportResult}
                            exportResultLoading={exportResultLoading}
                        />
                    </Box>
                </Container>
            </Box>
        </>
    )
}
Results.getLayout = (page) => (
    <DashboardLayout title="Examination">
        {page}
    </DashboardLayout>
);

export default Results;

export async function getServerSideProps({ req }) {
    let resultList = []
    try {
        const { data } = await axios.get(`${process.env.api}/school/exam/student/results/?page=1` , {
            headers: {
                Authorization: `Bearer ${req.cookies['accessToken']}`,
            },
        })
        resultList = data
    } catch (_e){
        resultList = []
    }
    return {
        props: {
            resultList: resultList
        }
    }
}
